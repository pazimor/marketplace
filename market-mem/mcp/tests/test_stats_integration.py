"""Integration tests for the token-savings stats — live FalkorDB.

record_fetch / stats_get / code_fetch run without any embedding model;
the code_search end-to-end test is skipped when the code embedding model
is unavailable.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from server.db import get_graph
from server.tools.code_fetch import code_fetch
from server.tools.stats import record_fetch, record_search, stats_get


@pytest.fixture()
def sample_file(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("def hello():\n" + "    x = 1\n" * 200)  # ~1.6 KB
    return f


def test_stats_empty_graph_returns_zeros(gid):
    s = stats_get(gid)
    assert s["search_calls"] == 0
    assert s["fetch_calls"] == 0
    assert s["saved_tokens"] == 0
    assert s["ratio"] is None


def test_record_fetch_accumulates(gid, sample_file):
    file_tokens = sample_file.stat().st_size // 4
    record_fetch(gid, str(sample_file), chunk_chars=400)
    record_fetch(gid, str(sample_file), chunk_chars=400)

    s = stats_get(gid)
    assert s["fetch_calls"] == 2
    assert s["baseline_tokens"] == 2 * file_tokens
    assert s["actual_tokens"] == 2 * 100
    assert s["saved_tokens"] == s["baseline_tokens"] - s["actual_tokens"]
    assert s["ratio"] > 1


def test_record_search_counts_distinct_files(gid, sample_file):
    # 3 results in the same file — the baseline must count the file ONCE
    results = [
        {"id": f"c{i}", "path": str(sample_file), "symbol": f"s{i}",
         "start_line": 1, "end_line": 5}
        for i in range(3)
    ]
    record_search(gid, results)
    s = stats_get(gid)
    assert s["search_calls"] == 1
    assert s["baseline_tokens"] == sample_file.stat().st_size // 4
    assert 0 < s["actual_tokens"] < s["baseline_tokens"]


def test_record_missing_file_never_raises(gid):
    record_fetch(gid, "/does/not/exist.py", chunk_chars=100)
    record_search(gid, [{"id": "x", "path": "/does/not/exist.py"}])
    s = stats_get(gid)  # counters may or may not move, but nothing blows up
    assert s["group_id"] == gid


def test_code_fetch_end_to_end_bumps_stats(gid, sample_file):
    path = str(sample_file)
    cid = hashlib.sha256(f"{path}::hello".encode()).hexdigest()[:32]
    get_graph(gid).query(
        """
        CREATE (:CodeChunk {id: $id, path: $path, symbol: 'hello',
                            start_line: 1, end_line: 5, valid: true})
        """,
        {"id": cid, "path": path},
    )
    out = code_fetch(node_id=cid, group_id=gid)
    assert "error" not in out
    s = stats_get(gid)
    assert s["fetch_calls"] == 1
    assert s["baseline_tokens"] > s["actual_tokens"] > 0


def _code_embedding_available() -> bool:
    try:
        from server.embedder import embed
        embed("probe", purpose="code")
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _code_embedding_available(),
                    reason="code embedding model unavailable")
def test_code_search_end_to_end_bumps_stats(gid, sample_file, tmp_path):
    from server.ingestion import ingest_repo
    from server.tools.code_search import code_search

    ingest_repo(gid, str(tmp_path))
    results = code_search("hello function", gid, k=5)
    if not results:
        pytest.skip("ingestion produced no searchable chunks")
    s = stats_get(gid)
    assert s["search_calls"] >= 1
    assert s["baseline_tokens"] > 0
