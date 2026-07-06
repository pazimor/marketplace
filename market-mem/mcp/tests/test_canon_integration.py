"""Integration tests — Canon Driven Development schema (live FalkorDB):
canon nodes, DETAILS links, dispatch bundle returned by task_claim, lint."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.tools.roadmap import (  # noqa: E402
    roadmap_apply, roadmap_lint, task_claim, task_release,
)


def _create(gid: str, kind: str, fields: dict) -> str:
    r = roadmap_apply(gid, [{"op": "create", "kind": kind, "fields": fields}],
                      author="it", worktree="")
    assert r["results"][0]["status"] == "created", r
    return r["results"][0]["id"]


def test_claim_returns_cdd_bundle(gid):
    task_id = _create(gid, "task", {
        "title": "add pagination", "type": "feature",
        "dod": "cursor pagination covered by tests", "due": "2026-08-01",
    })
    dep_id = _create(gid, "task", {"title": "schema migration", "type": "infra"})
    canon_id = _create(gid, "canon", {
        "title": "API contract",
        "description": "GET /items?cursor=<id>&limit=<=100; response {items, next_cursor}",
        "status": "active",
    })
    obsolete_id = _create(gid, "canon", {
        "title": "old offset contract", "description": "…", "status": "obsolete",
    })
    r = roadmap_apply(gid, [
        {"op": "link", "type": "DETAILS", "from": canon_id, "to": task_id},
        {"op": "link", "type": "DETAILS", "from": obsolete_id, "to": task_id},
        {"op": "link", "type": "DEPENDS_ON", "from": task_id, "to": dep_id},
    ])
    assert all(x["status"] == "linked" for x in r["results"]), r

    claim = task_claim(task_id, gid, user="it", worktree="/tmp/wt")
    assert claim["status"] == "claimed"
    assert claim["task"]["dod"] == "cursor pagination covered by tests"
    assert claim["task"]["due"] == "2026-08-01"
    assert claim["depends_on"] == [dep_id]
    # obsolete canon is excluded from the dispatch bundle
    assert [c["id"] for c in claim["canon"]] == [canon_id]
    assert "next_cursor" in claim["canon"][0]["description"]

    task_release(task_id, gid, user="it")


def test_details_edge_validation(gid):
    t1 = _create(gid, "task", {"title": "a", "type": "chore"})
    t2 = _create(gid, "task", {"title": "b", "type": "chore"})
    # DETAILS only goes Canon -> Task/Spec
    r = roadmap_apply(gid, [{"op": "link", "type": "DETAILS", "from": t1, "to": t2}])
    assert r["results"][0]["status"] == "error"


def test_lint_flags_detached_canon(gid):
    _create(gid, "canon", {"title": "floating canon", "description": "…"})
    lint = roadmap_lint(gid)
    assert any("DETAILS nothing" in w for w in lint["warnings"])
