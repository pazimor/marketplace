"""
Write-side memory tools.
These are hidden from the master agent — exposed only to haiku and for debug.
Dedup check before insert: skip if a very similar fact already exists (cosine > 0.92).
"""
from __future__ import annotations

import time
import uuid

from ..config import config
from ..db import get_graph
from ..embedder import embed
from ..schema import ensure_schema

_DEDUP_THRESHOLD = 0.92
_RETENTION_MS = 30 * 24 * 3_600_000   # 30 days


def memory_add(
    content: str,
    group_id: str,
    fact_type: str = "fact",
    anchor: str | None = None,
    valid_from: int | None = None,
) -> dict:
    ensure_schema(group_id)
    g = get_graph(group_id)
    now = int(time.time() * 1000)
    vec = embed(content, purpose="memory")

    # Dedup: check cosine similarity against existing valid facts
    dup = g.query(
        """
        CALL db.idx.vector.queryNodes('MemoryEpisode', 'emb', 1, vecf32($vec))
        YIELD node, score
        WHERE node.valid_from <= $now
          AND (node.invalid_at IS NULL OR node.invalid_at > $now)
        RETURN node.id, score
        LIMIT 1
        """,
        {"vec": vec, "now": now},
    )
    if dup.result_set:
        top_id, top_score = dup.result_set[0]
        if top_score >= _DEDUP_THRESHOLD:
            return {"status": "duplicate", "existing_id": top_id, "score": top_score}

    mid = str(uuid.uuid4())
    vf = valid_from if valid_from is not None else now
    g.query(
        """
        CREATE (:MemoryEpisode {
            id:               $id,
            group_id:         $gid,
            content:          $content,
            type:             $type,
            emb:              vecf32($emb),
            emb_model:        $model,
            emb_dim:          $dim,
            anchor:           $anchor,
            source:           'haiku',
            valid_from:       $vf,
            invalid_at:       null,
            immune:           false,
            created_at:       $now,
            last_accessed_at: $now,
            access_count:     0
        })
        """,
        {
            "id": mid,
            "gid": group_id,
            "content": content,
            "type": fact_type,
            "emb": vec,
            "model": config.MEMORY_EMBED_MODEL,
            "dim": len(vec),
            "anchor": anchor,
            "vf": vf,
            "now": now,
        },
    )

    # Optionally link to CodeChunk if anchor exists
    if anchor:
        g.query(
            """
            MATCH (m:MemoryEpisode {id: $mid})
            MATCH (c:CodeChunk {symbol: $sym, valid: true})
            MERGE (m)-[:ANCHORED_TO]->(c)
            """,
            {"mid": mid, "sym": anchor},
        )

    return {"status": "created", "id": mid}


def memory_immunize(memory_id: str, group_id: str) -> dict:
    g = get_graph(group_id)
    g.query("MATCH (m:MemoryEpisode {id: $id}) SET m.immune = true", {"id": memory_id})
    return {"status": "ok", "id": memory_id, "immune": True}


def memory_release(memory_id: str, group_id: str) -> dict:
    g = get_graph(group_id)
    g.query("MATCH (m:MemoryEpisode {id: $id}) SET m.immune = false", {"id": memory_id})
    return {"status": "ok", "id": memory_id, "immune": False}


def memory_extend(memory_id: str, group_id: str, days: int) -> dict:
    g = get_graph(group_id)
    extra_ms = days * 24 * 3_600_000
    g.query(
        """
        MATCH (m:MemoryEpisode {id: $id})
        SET m.created_at  = m.created_at  + $ms,
            m.invalid_at  = CASE WHEN m.invalid_at IS NOT NULL
                                 THEN m.invalid_at + $ms ELSE null END
        """,
        {"id": memory_id, "ms": extra_ms},
    )
    return {"status": "ok", "id": memory_id, "extended_days": days}
