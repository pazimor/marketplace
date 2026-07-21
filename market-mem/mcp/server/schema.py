"""FalkorDB schema initialisation for a project graph."""
from __future__ import annotations

import time

from .config import config
from .db import get_graph

SCHEMA_VERSION = 5

# Fields covered by the CodeChunk full-text index.  rel_path (repo-relative
# path, forward slashes) makes path tokens like "CuteSoft_Client" searchable.
_CODECHUNK_FT_FIELDS = ("symbol", "signature", "rel_path")

# Executed once per new graph.  FalkorDB silently ignores duplicate index creation.
_INIT_QUERIES = [
    # Vector indexes (fixed MAX_DIM — padding-zero preserves cosine similarity)
    f"CREATE VECTOR INDEX FOR (c:CodeChunk) ON (c.emb) OPTIONS {{dimension: {config.MAX_DIM}, similarityFunction: 'cosine'}}",
    f"CREATE VECTOR INDEX FOR (m:MemoryEpisode) ON (m.emb) OPTIONS {{dimension: {config.MAX_DIM}, similarityFunction: 'cosine'}}",
    # Full-text (lexical — for exact identifier lookup and hybrid retrieval)
    "CALL db.idx.fulltext.createNodeIndex('CodeChunk', "
    + ", ".join(f"'{f}'" for f in _CODECHUNK_FT_FIELDS) + ")",
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
    "CREATE INDEX FOR (m:MemoryEpisode) ON (m.kind)",
    # Distillation ledger (SessionStart transcript processing)
    "CREATE INDEX FOR (s:ProcessedSession) ON (s.id)",
    "CREATE INDEX FOR (s:ProcessedSession) ON (s.group_id)",
    # Phase 5B — call graph
    "CREATE INDEX FOR (f:FileNode) ON (f.id)",
    "CREATE INDEX FOR (f:FileNode) ON (f.path)",
    "CREATE INDEX FOR (f:FileNode) ON (f.group_id)",
    "CREATE INDEX FOR (c:CodeChunk) ON (c.symbol)",
    # term_name = last dotted segment of symbol — serves indexed callee
    # resolution in graph_builder (ENDS WITH is not index-served)
    "CREATE INDEX FOR (c:CodeChunk) ON (c.term_name)",
    "CREATE INDEX FOR (c:CodeChunk) ON (c.path)",
    # Roadmap layer (Spec / Milestone / Task / Canon)
    "CREATE INDEX FOR (c:Canon) ON (c.id)",
    "CREATE INDEX FOR (s:Spec) ON (s.id)",
    "CREATE INDEX FOR (m:Milestone) ON (m.id)",
    "CREATE INDEX FOR (t:Task) ON (t.id)",
    "CREATE INDEX FOR (t:Task) ON (t.status)",
    "CREATE INDEX FOR (t:Task) ON (t.claimed_by)",
]


def _migrate_codechunk_fulltext(g) -> None:
    """
    FalkorDB silently ignores duplicate full-text index creation, so a graph
    created before rel_path was added keeps its old ('symbol','signature')
    index forever.  Detect that via db.indexes() and drop + recreate.
    Dropping the full-text index leaves the vector index on the same label
    untouched (verified against a live FalkorDB).
    """
    try:
        res = g.query("CALL db.indexes()")
    except Exception:
        return  # no indexes yet — creation below will do the right thing

    for row in res.result_set:
        label, types = row[0], row[2]  # types: {property: [index_types]}
        if label != "CodeChunk":
            continue
        ft_fields = {prop for prop, kinds in dict(types).items() if "FULLTEXT" in kinds}
        if ft_fields and not set(_CODECHUNK_FT_FIELDS).issubset(ft_fields):
            try:
                g.query("CALL db.idx.fulltext.drop('CodeChunk')")
            except Exception:
                pass  # recreation below is still attempted


def _backfill_term_name(g) -> None:
    """Migration: graphs created before term_name was added need it derived
    from symbol (last dotted segment).  Batched so a 500k-chunk graph never
    runs one giant SET.  split()/last() verified against a live FalkorDB.
    """
    while True:
        try:
            res = g.query(
                """
                MATCH (c:CodeChunk)
                WHERE c.term_name IS NULL AND c.symbol IS NOT NULL
                WITH c LIMIT 10000
                SET c.term_name = last(split(c.symbol, '.'))
                RETURN count(c)
                """
            )
        except Exception:
            return  # no CodeChunk label yet, or transient error — non-fatal
        n = res.result_set[0][0] if res.result_set else 0
        if not n:
            return


def ensure_schema(group_id: str) -> None:
    """Create indexes and Project singleton if not present."""
    g = get_graph(group_id)

    _migrate_codechunk_fulltext(g)

    for q in _INIT_QUERIES:
        try:
            g.query(q)
        except Exception:
            pass  # index already exists

    _backfill_term_name(g)

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
