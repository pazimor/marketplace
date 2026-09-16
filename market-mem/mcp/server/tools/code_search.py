"""
Hybrid code search: vector (semantic) + full-text (lexical) fused with RRF.

Result contract (adoption-driven, see route_stats):
  - every hit carries a `snippet` (first lines of the chunk, sliced from the
    bind-mounted source file) so a hit is judgeable without a follow-up
    code_fetch/Read;
  - native scores are exposed (`vec_similarity`, `text_score`) instead of the
    opaque cumulated RRF number (kept as `rank_score`, ranking only);
  - the envelope carries an honest non-exhaustiveness note: semantic top-k
    can silently miss occurrences — Grep remains the literal sweep tool.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from ..config import config
from ..db import get_graph
from ..embedder import embed
from ..paths import indexed_commit, resolve

SNIPPET_LINES = 8

NOTE = (
    "top-k hybrid (semantic+keyword) search — NOT exhaustive. For a complete "
    "literal sweep (rename, refactor, count of occurrences) use Grep."
)


def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


def _ft_query(query: str) -> str:
    """Build an OR full-text query from the raw user query.

    RediSearch ANDs space-separated terms, so a multi-word conceptual query
    ("distiller ledger idempotence") matches nothing lexically. OR-ing the
    terms lets each contribute; RRF ranks the overlap on top.
    """
    terms = re.findall(r"[A-Za-z0-9_]{2,}", query)
    seen: list[str] = []
    for t in terms:
        if t.lower() not in {s.lower() for s in seen}:
            seen.append(t)
    return "|".join(seen) if seen else query


def _snippet(path: str, start_line: int, end_line: int,
             cache: dict[str, list[str] | None], group_id: str) -> str | None:
    """First SNIPPET_LINES of the chunk, sliced from the source file.

    *path* is the stored repo-relative path; it is resolved against the roots
    this server can actually read (working tree, then git mirror).

    Best-effort: returns None when the file is unreadable or has shifted
    (stale index) — never raises."""
    try:
        if path not in cache:
            abs_path = resolve(group_id, path)
            cache[path] = (Path(abs_path).read_text(errors="replace").splitlines()
                           if abs_path else None)
        lines = cache[path]
        if lines is None:
            return None
        sl = max(1, int(start_line))
        el = min(len(lines), int(end_line), sl + SNIPPET_LINES - 1)
        if sl > len(lines):
            return None
        return "\n".join(lines[sl - 1 : el])
    except OSError:
        cache[path] = None
        return None


def code_search(query: str, group_id: str, k: int = 10) -> dict:
    g = get_graph(group_id)
    vec = embed(query, purpose="code")

    # --- Vector KNN ---
    vec_result = g.query(
        f"""
        CALL db.idx.vector.queryNodes('CodeChunk', 'emb', $k, vecf32($vec))
        YIELD node, score
        WHERE node.valid = true
        RETURN node.id, node.path, node.symbol, node.kind, node.lang,
               node.signature, node.start_line, node.end_line, score
        ORDER BY score
        LIMIT $k
        """,
        {"vec": vec, "k": k * 2},
    )

    # --- Full-text (OR over terms — see _ft_query) ---
    ft_result = g.query(
        f"""
        CALL db.idx.fulltext.queryNodes('CodeChunk', $q)
        YIELD node, score
        WHERE node.valid = true
        RETURN node.id, node.path, node.symbol, node.kind, node.lang,
               node.signature, node.start_line, node.end_line, score
        LIMIT $k
        """,
        {"q": _ft_query(query), "k": k * 2},
    )

    # --- RRF fusion (ranking) + native scores (relevance signal) ---
    scores: dict[str, float] = {}
    meta: dict[str, dict] = {}

    def _register(rows, source: str):
        for rank, row in enumerate(rows):
            nid, path, symbol, kind, lang, sig, sl, el, sc = row
            scores[nid] = scores.get(nid, 0.0) + _rrf_score(rank)
            if nid not in meta:
                meta[nid] = {
                    "id": nid,
                    "path": path,
                    "symbol": symbol,
                    "kind": kind,
                    "lang": lang,
                    "signature": sig,
                    "start_line": sl,
                    "end_line": el,
                }
            if source == "vec":
                # FalkorDB yields cosine DISTANCE (0 = identical) — invert.
                meta[nid]["vec_similarity"] = round(1.0 - float(sc), 4)
            else:
                meta[nid]["text_score"] = round(float(sc), 4)

    _register(vec_result.result_set, "vec")
    _register(ft_result.result_set, "ft")

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]

    # Bump access metadata
    now = int(time.time() * 1000)
    for nid, _ in ranked:
        g.query(
            "MATCH (c:CodeChunk {id: $id}) SET c.last_accessed_at = $now",
            {"id": nid, "now": now},
        )

    file_cache: dict[str, list[str] | None] = {}
    out = []
    for nid, sc in ranked:
        if nid not in meta:
            continue
        hit = meta[nid] | {"rank_score": round(sc, 5)}
        hit["snippet"] = _snippet(hit["path"], hit["start_line"], hit["end_line"],
                                  file_cache, group_id)
        out.append(hit)

    from .stats import record_search
    record_search(group_id, out)

    # Callers must know how fresh the index is: a mirror-indexed project
    # reflects the last pushed commit, not anyone's working tree.
    commit = indexed_commit(group_id)
    out_doc = {"results": out, "note": NOTE}
    if commit:
        out_doc["indexed_commit"] = commit
    return out_doc
