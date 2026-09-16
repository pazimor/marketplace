"""
Token-savings statistics for the code RAG (approximation, 1 token ~= 4 chars).

Baseline = what the agent would have read WITHOUT the RAG:
  - code_search: the full content of every distinct file in the top-k results
  - code_fetch:  the full file instead of the chunk slice
Actual = what the tool really returned.

Counters accumulate on the Project node (one per graph). Best-effort by
design: a stats failure must never break a search, and file sizes come from
the read-only repo bind-mount (missing file -> skipped).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from ..db import get_graph
from ..paths import resolve

log = logging.getLogger(__name__)

_CHARS_PER_TOKEN = 4


def _tokens(chars: int) -> int:
    return max(0, chars) // _CHARS_PER_TOKEN


def _file_tokens(path: str, group_id: str | None = None) -> int:
    """Token cost of reading the whole file, the baseline code RAG saves against.

    Stored paths are repo-relative, so they need resolving before stat()."""
    try:
        target = resolve(group_id, path) if group_id else path
        if not target:
            return 0
        return _tokens(Path(target).stat().st_size)
    except OSError:
        return 0


def _bump(group_id: str, field: str, baseline: int, actual: int) -> None:
    if baseline <= 0 and actual <= 0:
        return
    g = get_graph(group_id)
    g.query(
        f"""
        MERGE (p:Project {{group_id: $gid}})
        SET p.{field}             = coalesce(p.{field}, 0) + 1,
            p.stats_baseline_tokens = coalesce(p.stats_baseline_tokens, 0) + $baseline,
            p.stats_actual_tokens   = coalesce(p.stats_actual_tokens, 0) + $actual,
            p.stats_updated_at      = $now
        """,
        {"gid": group_id, "baseline": baseline, "actual": actual,
         "now": int(time.time() * 1000)},
    )


def record_search(group_id: str, results: list[dict]) -> None:
    """Accumulate stats for one code_search call. Never raises."""
    try:
        if not results:
            return
        baseline = sum(_file_tokens(p, group_id) for p in {r.get("path") for r in results} if p)
        actual = _tokens(len(json.dumps(results, default=str)))
        _bump(group_id, "stats_search_calls", baseline, actual)
    except Exception as exc:
        log.debug("record_search skipped: %s", exc)


def record_fetch(group_id: str, path: str, chunk_chars: int) -> None:
    """Accumulate stats for one code_fetch call. Never raises."""
    try:
        _bump(group_id, "stats_fetch_calls", _file_tokens(path), _tokens(chunk_chars))
    except Exception as exc:
        log.debug("record_fetch skipped: %s", exc)


def stats_get(group_id: str) -> dict:
    """Current counters + derived savings for one project graph."""
    g = get_graph(group_id)
    res = g.query(
        """
        MATCH (p:Project {group_id: $gid})
        RETURN coalesce(p.stats_search_calls, 0),
               coalesce(p.stats_fetch_calls, 0),
               coalesce(p.stats_baseline_tokens, 0),
               coalesce(p.stats_actual_tokens, 0),
               p.stats_updated_at
        """,
        {"gid": group_id},
    )
    if not res.result_set:
        searches = fetches = baseline = actual = 0
        updated_at = None
    else:
        searches, fetches, baseline, actual, updated_at = res.result_set[0]
    return {
        "group_id": group_id,
        "search_calls": searches,
        "fetch_calls": fetches,
        "baseline_tokens": baseline,
        "actual_tokens": actual,
        "saved_tokens": max(0, baseline - actual),
        "ratio": round(baseline / actual, 1) if actual else None,
        "updated_at": updated_at,
    }
