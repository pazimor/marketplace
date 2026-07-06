"""Integration tests — distillation ledger + memory kinds (live FalkorDB)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.tools.memory_write import memory_add, memory_delete  # noqa: E402
from server.tools.sessions import session_mark_processed, sessions_processed  # noqa: E402


def test_ledger_roundtrip(gid):
    assert sessions_processed(gid)["ids"] == []

    r = session_mark_processed(gid, "sess-a", "done", facts_written=3)
    assert r["status"] == "ok"
    session_mark_processed(gid, "sess-b", "failed")

    out = sessions_processed(gid)
    entries = {e["session_id"]: e for e in out["sessions"]}
    assert entries["sess-a"]["status"] == "done"
    assert entries["sess-a"]["facts_written"] == 3
    assert entries["sess-b"]["status"] == "failed"

    # a retry overwrites the failed entry (MERGE, no duplicate node)
    session_mark_processed(gid, "sess-b", "done", facts_written=1)
    out = sessions_processed(gid)
    b_entries = [e for e in out["sessions"] if e["session_id"] == "sess-b"]
    assert len(b_entries) == 1
    assert b_entries[0]["status"] == "done"
    assert b_entries[0]["facts_written"] == 1


def test_ledger_rejects_bad_status(gid):
    r = session_mark_processed(gid, "sess-x", "bogus")
    assert r["status"] == "error"


def test_memory_add_kind_and_delete(gid):
    r = memory_add("user always wants ruff run before commit", gid,
                   fact_type="convention", kind="preference", source="distiller")
    assert r["status"] == "created"

    bad = memory_add("some fact", gid, kind="bogus")
    assert bad["status"] == "error"

    d = memory_delete(r["id"], gid)
    assert d["status"] == "deleted"
    assert memory_delete(r["id"], gid)["status"] == "error"  # already gone
