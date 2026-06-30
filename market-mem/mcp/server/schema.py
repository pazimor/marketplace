"""FalkorDB schema initialisation for a project graph."""
from __future__ import annotations

import time

from .config import config
from .db import get_graph

SCHEMA_VERSION = 2

# Executed once per new graph.  FalkorDB silently ignores duplicate index creation.
_INIT_QUERIES = [
    # Vector indexes (fixed MAX_DIM — padding-zero preserves cosine similarity)
    f"CREATE VECTOR INDEX FOR (c:CodeChunk) ON (c.emb) OPTIONS {{dimension: {config.MAX_DIM}, similarityFunction: 'cosine'}}",
    f"CREATE VECTOR INDEX FOR (m:MemoryEpisode) ON (m.emb) OPTIONS {{dimension: {config.MAX_DIM}, similarityFunction: 'cosine'}}",
    # Full-text (lexical — for exact identifier lookup and hybrid retrieval)
    "CALL db.idx.fulltext.createNodeIndex('CodeChunk', 'symbol', 'signature')",
    "CALL db.idx.fulltext.createNodeIndex('MemoryEpisode', 'content')",
    # Range indexes for temporal purge and incremental re-embed
    "CREATE INDEX FOR (m:MemoryEpisode) ON (m.invalid_at)",
    "CREATE INDEX FOR (m:MemoryEpisode) ON (m.created_at)",
    "CREATE INDEX FOR (m:MemoryEpisode) ON (m.last_accessed_at)",
    "CREATE INDEX FOR (c:CodeChunk) ON (c.updated_at)",
    # Exact-match dedup / upsert
    "CREATE INDEX FOR (c:CodeChunk) ON (c.id)",
    "CREATE INDEX FOR (c:CodeChunk) ON (c.content_hash)",
    "CREATE INDEX FOR (m:MemoryEpisode) ON (m.id)",
    # Phase 5B — call graph
    "CREATE INDEX FOR (f:FileNode) ON (f.id)",
    "CREATE INDEX FOR (f:FileNode) ON (f.path)",
    "CREATE INDEX FOR (f:FileNode) ON (f.group_id)",
    "CREATE INDEX FOR (c:CodeChunk) ON (c.symbol)",
]


def ensure_schema(group_id: str) -> None:
    """Create indexes and Project singleton if not present."""
    g = get_graph(group_id)

    for q in _INIT_QUERIES:
        try:
            g.query(q)
        except Exception:
            pass  # index already exists

    # Upsert Project singleton
    now = int(time.time() * 1000)
    g.query(
        """
        MERGE (p:Project {group_id: $gid})
        SET p.schema_version = $ver,
            p.created_at     = COALESCE(p.created_at, $now)
""",
        {"gid": group_id, "ver": SCHEMA_VERSION, "now": now},
    )

    # Register embedding models (idempotent)
    for purpose, model, dim in [
        ("code", config.CODE_EMBED_MODEL, 768),
        ("memory", config.MEMORY_EMBED_MODEL, 768),
    ]:
        g.query(
            """
            MERGE (m:EmbeddingModel {id: $id})
            SET m.name       = $name,
                m.purpose    = $purpose,
                m.dim        = $dim,
                m.metric     = 'cosine',
                m.active     = true,
                m.created_at = COALESCE(m.created_at, $now)
""",
            {"id": f"{model}@1.0", "name": model, "purpose": purpose, "dim": dim, "now": now},
        )
