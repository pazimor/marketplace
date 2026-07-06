"""Integration tests for the memory write tools — live FalkorDB.

The guard tests (missing id, bad days) run without any embedding model.
The end-to-end add/search tests need the memory embedding model and are
skipped automatically when it is unavailable (e.g. cold container).
"""
from __future__ import annotations

import pytest

from server.tools.memory_write import (
    memory_add,
    memory_extend,
    memory_immunize,
    memory_release,
)
from server.db import get_graph


def _embedding_available() -> bool:
    try:
        from server.embedder import embed
        embed("probe", purpose="memory")
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Guards — no embedding needed
# ---------------------------------------------------------------------------

def test_immunize_missing_id_errors(gid):
    r = memory_immunize("no-such-id", gid)
    assert r["status"] == "error"
    assert "not found" in r["error"]


def test_release_missing_id_errors(gid):
    assert memory_release("no-such-id", gid)["status"] == "error"


def test_extend_missing_id_errors(gid):
    assert memory_extend("no-such-id", gid, 10)["status"] == "error"


@pytest.mark.parametrize("days", [0, -1, -999])
def test_extend_rejects_non_positive_days(gid, days):
    r = memory_extend("whatever", gid, days)
    assert r["status"] == "error"
    assert "positive" in r["error"]


# ---------------------------------------------------------------------------
# End-to-end — needs the memory embedding model
# ---------------------------------------------------------------------------

needs_embedding = pytest.mark.skipif(
    not _embedding_available(), reason="memory embedding model unavailable"
)


@needs_embedding
def test_add_immunize_extend_lifecycle(gid):
    r = memory_add("the installer CLI is called market, not mem", gid, "decision")
    assert r["status"] == "created", r
    mid = r["id"]

    assert memory_immunize(mid, gid) == {"status": "ok", "id": mid, "immune": True}
    assert memory_release(mid, gid)["immune"] is False

    g = get_graph(gid)
    before = g.query(
        "MATCH (m:MemoryEpisode {id: $id}) RETURN m.created_at", {"id": mid}
    ).result_set[0][0]
    assert memory_extend(mid, gid, 7)["status"] == "ok"
    after = g.query(
        "MATCH (m:MemoryEpisode {id: $id}) RETURN m.created_at", {"id": mid}
    ).result_set[0][0]
    assert after - before == 7 * 24 * 3_600_000


@needs_embedding
def test_add_dedups_near_identical_facts(gid):
    content = "vector index uses MAX_DIM 2048 with zero padding"
    first = memory_add(content, gid, "fact")
    assert first["status"] == "created"
    second = memory_add(content, gid, "fact")
    assert second["status"] == "duplicate"
    assert second["existing_id"] == first["id"]
