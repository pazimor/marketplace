"""
Hybrid episodic memory search: vector + full-text, RRF fusion.
Filters out invalidated / expired facts.
"""
from __future__ import annotations

import time

from ..db import get_graph
from ..embedder import embed
from .code_search import _ft_query

NOTE = (
    "top-k semantic search over past facts/decisions — NOT exhaustive. "
    "An empty result just means nothing recorded matches; it is cheap and OK."
)


def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


def memory_search(query: str, group_id: str, k: int = 10) -> dict:
    g = get_graph(group_id)
    now = int(time.time() * 1000)
    vec = embed(query, purpose="memory")

    # --- Vector KNN (valid facts only) ---
    vec_result = g.query(
        """
        CALL db.idx.vector.queryNodes('MemoryEpisode', 'emb', $k, vecf32($vec))
        YIELD node, score
        WHERE node.valid_from <= $now
          AND (node.invalid_at IS NULL OR node.invalid_at > $now)
        RETURN node.id, node.content, node.type, node.anchor,
               node.created_at, node.valid_from, node.invalid_at, score
        ORDER BY score
        LIMIT $k
        """,
        {"vec": vec, "k": k * 2, "now": now},
    )

    # --- Full-text ---
    ft_result = g.query(
        """
        CALL db.idx.fulltext.queryNodes('MemoryEpisode', $q)
        YIELD node, score
        WHERE node.valid_from <= $now
          AND (node.invalid_at IS NULL OR node.invalid_at > $now)
        RETURN node.id, node.content, node.type, node.anchor,
               node.created_at, node.valid_from, node.invalid_at, score
        LIMIT $k
        """,
        {"q": _ft_query(query), "k": k * 2, "now": now},
    )

    scores: dict[str, float] = {}
    meta: dict[str, dict] = {}

    def _register(rows, source: str):
        for rank, row in enumerate(rows):
            mid, content, mtype, anchor, created_at, valid_from, invalid_at, sc = row
            scores[mid] = scores.get(mid, 0.0) + _rrf_score(rank)
            if mid not in meta:
                meta[mid] = {
                    "id": mid,
                    "content": content,
                    "type": mtype,
                    "anchor": anchor,
                    "created_at": created_at,
                }
            if source == "vec":
                # FalkorDB yields cosine DISTANCE (0 = identical) — invert.
                meta[mid]["vec_similarity"] = round(1.0 - float(sc), 4)
            else:
                meta[mid]["text_score"] = round(float(sc), 4)

    _register(vec_result.result_set, "vec")
    _register(ft_result.result_set, "ft")

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]

    # Update access stats
    for mid, _ in ranked:
        g.query(
            """
            MATCH (m:MemoryEpisode {id: $id})
            SET m.last_accessed_at = $now,
                m.access_count = coalesce(m.access_count, 0) + 1
            """,
            {"id": mid, "now": now},
        )

    hits = [meta[mid] | {"rank_score": round(sc, 5)} for mid, sc in ranked if mid in meta]
    return {"results": hits, "note": NOTE}


def memory_query(query: str, group_id: str, symbol: str | None = None) -> list[dict]:
    """Targeted lookup: semantic search filtered to facts anchored to *symbol*."""
    g = get_graph(group_id)
    now = int(time.time() * 1000)
    vec = embed(query, purpose="memory")

    if symbol:
        result = g.query(
            """
            CALL db.idx.vector.queryNodes('MemoryEpisode', 'emb', 20, vecf32($vec))
            YIELD node, score
            WHERE node.anchor = $sym
              AND node.valid_from <= $now
              AND (node.invalid_at IS NULL OR node.invalid_at > $now)
            RETURN node.id, node.content, node.type, node.anchor,
                   node.created_at, score
            ORDER BY score
            LIMIT 10
            """,
            {"vec": vec, "sym": symbol, "now": now},
        )
    else:
        result = g.query(
            """
            CALL db.idx.vector.queryNodes('MemoryEpisode', 'emb', 20, vecf32($vec))
            YIELD node, score
            WHERE node.valid_from <= $now
              AND (node.invalid_at IS NULL OR node.invalid_at > $now)
            RETURN node.id, node.content, node.type, node.anchor,
                   node.created_at, score
            ORDER BY score
            LIMIT 10
            """,
            {"vec": vec, "now": now},
        )

    return [
        {"id": r[0], "content": r[1], "type": r[2], "anchor": r[3],
         "created_at": r[4], "score": r[5]}
        for r in result.result_set
    ]
