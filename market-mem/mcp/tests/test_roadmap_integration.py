"""Integration tests for the roadmap layer — live FalkorDB, disposable graph.

Covers the write-time guards (invalid enums, done-via-update, ghost
blocked_reason), the claim/release protocol, link constraints, deletes,
lint, backlog and export coherence.
"""
from __future__ import annotations

from server.tools.roadmap import (
    backlog_get,
    roadmap_apply,
    roadmap_export,
    roadmap_impact,
    roadmap_lint,
    task_claim,
    task_release,
)


def _create(gid, kind, **fields):
    r = roadmap_apply(gid, [{"op": "create", "kind": kind, "fields": fields}])
    res = r["results"][0]
    assert res["status"] == "created", res
    return res["id"]


# ---------------------------------------------------------------------------
# Write-time validation
# ---------------------------------------------------------------------------

def test_create_task_happy_path(gid):
    tid = _create(gid, "task", title="build the thing", type="feature")
    bl = backlog_get(gid)
    assert [t["id"] for t in bl["tasks"]["todo"]] == [tid]


def test_create_rejects_invalid_status(gid):
    r = roadmap_apply(gid, [{"op": "create", "kind": "task",
                             "fields": {"title": "x", "status": "banana"}}])
    res = r["results"][0]
    assert res["status"] == "error"
    assert "invalid status" in res["error"]
    assert backlog_get(gid)["tasks"] == {}  # nothing entered the graph


def test_create_rejects_invalid_task_type(gid):
    r = roadmap_apply(gid, [{"op": "create", "kind": "task",
                             "fields": {"title": "x", "type": "sorcery"}}])
    assert r["results"][0]["status"] == "error"
    assert "invalid task type" in r["results"][0]["error"]


def test_update_rejects_invalid_status(gid):
    tid = _create(gid, "task", title="t")
    r = roadmap_apply(gid, [{"op": "update", "id": tid,
                             "fields": {"status": "banana"}}])
    assert r["results"][0]["status"] == "error"


def test_update_cannot_mark_task_done(gid):
    tid = _create(gid, "task", title="t")
    r = roadmap_apply(gid, [{"op": "update", "id": tid,
                             "fields": {"status": "done"}}])
    res = r["results"][0]
    assert res["status"] == "error"
    assert "task_release" in res["error"]


def test_blocked_reason_requires_blocked_status(gid):
    tid = _create(gid, "task", title="t")
    r = roadmap_apply(gid, [{"op": "update", "id": tid,
                             "fields": {"status": "todo",
                                        "blocked_reason": "nope"}}])
    assert r["results"][0]["status"] == "error"


def test_unblocking_clears_blocked_reason(gid):
    tid = _create(gid, "task", title="t")
    roadmap_apply(gid, [{"op": "update", "id": tid,
                         "fields": {"status": "blocked",
                                    "blocked_reason": "waiting on X"}}])
    roadmap_apply(gid, [{"op": "update", "id": tid, "fields": {"status": "todo"}}])
    task = backlog_get(gid)["tasks"]["todo"][0]
    assert task["blocked_reason"] is None
    assert "blocked" not in roadmap_export(gid)


# ---------------------------------------------------------------------------
# Claim / release protocol
# ---------------------------------------------------------------------------

def test_claim_release_lifecycle(gid):
    tid = _create(gid, "task", title="t")
    assert task_claim(tid, gid, "alice", "/wt/a")["status"] == "claimed"
    assert backlog_get(gid)["tasks"]["in_progress"][0]["claimed_by"] == "alice"

    assert task_release(tid, gid, "alice", done=False)["status"] == "released"
    assert backlog_get(gid)["tasks"]["todo"][0]["claimed_by"] is None

    task_claim(tid, gid, "alice", "/wt/a")
    assert task_release(tid, gid, "alice", done=True)["status"] == "released"
    assert backlog_get(gid, include_done=True)["tasks"]["done"][0]["id"] == tid


def test_claim_conflict_refused(gid):
    tid = _create(gid, "task", title="t")
    task_claim(tid, gid, "alice", "/wt/a")
    assert task_claim(tid, gid, "bob", "/wt/b")["status"] == "refused"
    # same user from another worktree is a conflict too
    assert task_claim(tid, gid, "alice", "/wt/other")["status"] == "refused"
    # same user + same worktree is a no-op re-claim
    assert task_claim(tid, gid, "alice", "/wt/a")["status"] == "claimed"


def test_done_requires_holding_the_claim(gid):
    tid = _create(gid, "task", title="t")
    r = task_release(tid, gid, "stranger", done=True)
    assert r["status"] == "refused"
    assert backlog_get(gid)["tasks"]["todo"], "task must still be todo"


def test_cannot_claim_done_task(gid):
    tid = _create(gid, "task", title="t")
    task_claim(tid, gid, "alice", "/wt/a")
    task_release(tid, gid, "alice", done=True)
    assert task_claim(tid, gid, "bob", "/wt/b")["status"] == "refused"


def test_release_missing_task_errors(gid):
    assert task_release("ROADMAP:TASK:999", gid, "alice")["status"] == "error"


# ---------------------------------------------------------------------------
# Links, deletes, impact
# ---------------------------------------------------------------------------

def test_self_dependency_rejected(gid):
    tid = _create(gid, "task", title="t")
    r = roadmap_apply(gid, [{"op": "link", "type": "DEPENDS_ON",
                             "from": tid, "to": tid}])
    assert r["results"][0]["status"] == "error"


def test_link_label_constraints(gid):
    tid = _create(gid, "task", title="t")
    sid = _create(gid, "spec", title="s")
    # Spec cannot IMPLEMENTS a Task (only Task -> Spec)
    r = roadmap_apply(gid, [{"op": "link", "type": "IMPLEMENTS",
                             "from": sid, "to": tid}])
    assert r["results"][0]["status"] == "error"
    r = roadmap_apply(gid, [{"op": "link", "type": "IMPLEMENTS",
                             "from": tid, "to": sid}])
    assert r["results"][0]["status"] == "linked"


def test_link_missing_endpoint_errors(gid):
    tid = _create(gid, "task", title="t")
    r = roadmap_apply(gid, [{"op": "link", "type": "PART_OF",
                             "from": tid, "to": "ROADMAP:MILESTONE:999"}])
    assert r["results"][0]["status"] == "error"


def test_delete_detaches_and_reports_edges(gid):
    a = _create(gid, "task", title="A")
    b = _create(gid, "task", title="B")
    roadmap_apply(gid, [{"op": "link", "type": "DEPENDS_ON", "from": a, "to": b}])
    r = roadmap_apply(gid, [{"op": "delete", "id": b}])
    res = r["results"][0]
    assert res["status"] == "deleted"
    assert res["detached_edges"] == 1
    assert backlog_get(gid)["tasks"]["todo"][0]["depends_on"] == []


def test_impact_traverses_dependents(gid):
    a = _create(gid, "task", title="A")
    b = _create(gid, "task", title="B")
    c = _create(gid, "task", title="C")
    roadmap_apply(gid, [
        {"op": "link", "type": "DEPENDS_ON", "from": b, "to": a},
        {"op": "link", "type": "DEPENDS_ON", "from": c, "to": b},
    ])
    dependents = {t["id"] for t in roadmap_impact(a, gid)["dependent_tasks"]}
    assert dependents == {b, c}


# ---------------------------------------------------------------------------
# Lint & export
# ---------------------------------------------------------------------------

def test_lint_detects_cycle_and_orphan_milestone(gid):
    a = _create(gid, "task", title="A")
    b = _create(gid, "task", title="B")
    _create(gid, "milestone", title="lonely")
    roadmap_apply(gid, [
        {"op": "link", "type": "DEPENDS_ON", "from": a, "to": b},
        {"op": "link", "type": "DEPENDS_ON", "from": b, "to": a},
    ])
    lint = roadmap_lint(gid)
    assert not lint["ok"]
    assert any("circular" in e for e in lint["errors"])
    assert any("orphan milestone" in e for e in lint["errors"])


def test_export_reflects_graph(gid):
    sid = _create(gid, "spec", title="the spec")
    mid = _create(gid, "milestone", title="v1")
    tid = _create(gid, "task", title="do it")
    roadmap_apply(gid, [
        {"op": "link", "type": "IMPLEMENTS", "from": tid, "to": sid},
        {"op": "link", "type": "PART_OF", "from": tid, "to": mid},
    ])
    md = roadmap_export(gid)
    assert "the spec" in md and "v1" in md
    assert f"`{tid}` do it" in md
    assert f"implements {sid}" in md
