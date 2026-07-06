"""Integration tests — Task→CodeChunk PRODUCED links (live FalkorDB)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.db import get_graph  # noqa: E402
from server.tools.roadmap import roadmap_apply, roadmap_impact, task_link_code  # noqa: E402


def _make_task(gid: str) -> str:
    r = roadmap_apply(gid, [{
        "op": "create", "kind": "task",
        "fields": {"title": "add pagination", "type": "feature",
                   "dod": "cursor pagination covered by tests"},
    }], author="it", worktree="")
    return r["results"][0]["id"]


def _make_chunk(gid: str, symbol: str) -> None:
    get_graph(gid).query(
        "CREATE (:CodeChunk {id: $id, group_id: $gid, symbol: $sym, "
        "path: 'api/list.py', valid: true})",
        {"id": f"chunk-{symbol}", "gid": gid, "sym": symbol},
    )


def test_task_link_code_roundtrip(gid):
    task_id = _make_task(gid)
    _make_chunk(gid, "api.list_items")

    r = task_link_code(task_id, gid, ["api.list_items", "api.not_ingested_yet"])
    assert r["status"] == "ok"
    assert r["linked"] == ["api.list_items"]
    assert r["missing"] == ["api.not_ingested_yet"]

    # idempotent: MERGE, no duplicate edge
    r2 = task_link_code(task_id, gid, ["api.list_items"])
    assert r2["linked"] == ["api.list_items"]
    edges = get_graph(gid).query(
        "MATCH (:Task {id: $tid})-[r:PRODUCED]->(:CodeChunk) RETURN count(r)",
        {"tid": task_id},
    ).result_set[0][0]
    assert edges == 1

    # exposed in roadmap_impact for the task
    impact = roadmap_impact(task_id, gid)
    assert impact["produced_code"] == [{"symbol": "api.list_items", "path": "api/list.py"}]


def test_task_link_code_unknown_task(gid):
    r = task_link_code("ROADMAP:TASK:999", gid, ["api.list_items"])
    assert r["status"] == "error"
