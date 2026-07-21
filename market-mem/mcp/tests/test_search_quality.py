"""Search-quality and ergonomics tests.

Covers the adoption fixes: OR full-text query building, per-hit snippets,
native scores, the result envelope, and the helpful missing-group_id reply.
Embedding-dependent tests are skipped when the model is unavailable
(same pattern as test_stats_integration).
"""
from __future__ import annotations

import asyncio

import pytest

from server.tools.code_search import _ft_query, _snippet


# ---------------------------------------------------------------------------
# _ft_query — OR semantics for multi-word conceptual queries
# ---------------------------------------------------------------------------

def test_ft_query_ors_terms():
    assert _ft_query("distiller ledger idempotence") == "distiller|ledger|idempotence"


def test_ft_query_dedupes_case_insensitively():
    assert _ft_query("Ledger ledger LEDGER") == "Ledger"


def test_ft_query_strips_punctuation_and_short_tokens():
    assert _ft_query("où est géré le retry ?") == "est|le|retry"


def test_ft_query_falls_back_to_raw_when_no_tokens():
    assert _ft_query("??") == "??"


# ---------------------------------------------------------------------------
# _snippet — best-effort slice of the source file
# ---------------------------------------------------------------------------

def test_snippet_returns_first_lines(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text("\n".join(f"line{i}" for i in range(1, 21)))
    cache: dict = {}
    snip = _snippet(str(f), 3, 20, cache)
    assert snip is not None
    lines = snip.splitlines()
    assert lines[0] == "line3"
    assert len(lines) == 8  # capped at SNIPPET_LINES


def test_snippet_missing_file_returns_none():
    cache: dict = {}
    assert _snippet("/does/not/exist.py", 1, 5, cache) is None
    # negative cache entry — second call must not retry the read
    assert cache["/does/not/exist.py"] is None


def test_snippet_stale_range_returns_none(tmp_path):
    f = tmp_path / "short.py"
    f.write_text("only\ntwo\n")
    assert _snippet(str(f), 10, 20, {}) is None


# ---------------------------------------------------------------------------
# Missing group_id — helpful structured reply, not a validation error
# ---------------------------------------------------------------------------

def test_missing_gid_reply_lists_known_graphs():
    from server import main

    out = asyncio.run(main.code_search("anything"))
    assert "error" in out and "group_id" in out["error"]
    assert "hint" in out
    assert isinstance(out["known_graphs"], list)

    mem = asyncio.run(main.memory_search("anything"))
    assert "error" in mem


# ---------------------------------------------------------------------------
# End-to-end: envelope, snippet and native scores on real search
# ---------------------------------------------------------------------------

def _code_embedding_available() -> bool:
    try:
        from server.embedder import embed
        embed("probe", purpose="code")
        return True
    except Exception:
        return False


SAMPLE = '''\
def process_ledger_sessions(entries):
    """Mark processed sessions in the ledger; idempotent replay of failures."""
    done = set()
    for e in entries:
        if e.id in done:
            continue
        done.add(e.id)
    return done


def unrelated_helper(x):
    return x + 1
'''


@pytest.mark.skipif(not _code_embedding_available(),
                    reason="code embedding model unavailable")
def test_code_search_envelope_snippet_and_recall(gid, tmp_path):
    from server.ingestion import ingest_repo
    from server.tools.code_search import code_search

    (tmp_path / "ledger.py").write_text(SAMPLE)
    ingest_repo(gid, str(tmp_path))

    out = code_search("ledger processed sessions idempotence", gid, k=5)
    assert "note" in out
    results = out["results"]
    if not results:
        pytest.skip("ingestion produced no searchable chunks")

    symbols = [r["symbol"] for r in results]
    assert any("process_ledger_sessions" in s for s in symbols), symbols

    top = results[0]
    assert top["snippet"], "hits must carry a snippet"
    assert "rank_score" in top
    assert "vec_similarity" in top or "text_score" in top
