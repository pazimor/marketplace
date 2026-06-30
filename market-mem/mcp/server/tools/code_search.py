"""
Hybrid code search: vector (semantic) + full-text (lexical) fused with RRF.
"""
from __future__ import annotations

import time

from ..config import config
from ..db import get_graph
from ..embedder import embed


def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


def code_search(query: str, group_id: str, k: int = 10) -> list[dict]:
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

    # --- Full-text ---
    ft_result = g.query(
        f"""
        CALL db.idx.fulltext.queryNodes('CodeChunk', $q)
        YIELD node, score
        WHERE node.valid = true
        RETURN node.id, node.path, node.symbol, node.kind, node.lang,
               node.signature, node.start_line, node.end_line, score
        LIMIT $k
        """,
        {"q": query, "k": k * 2},
    )

    # --- RRF fusion ---
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

    return [meta[nid] | {"score": sc} for nid, sc in ranked if nid in meta]
