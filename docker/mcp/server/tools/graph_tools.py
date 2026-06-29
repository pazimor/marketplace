"""
Graph traversal MCP tools (Phase 5B).

impact_of    — which symbols are impacted if *symbol* changes?
callers_of   — which symbols directly (or transitively) call *symbol*?
imports_of   — which files does *file* import (directly)?

All traversals use FalkorDB's native variable-length relationship syntax.
Depth cap: max 10 hops to prevent runaway traversal on dense graphs.
"""
from __future__ import annotations

from ..db import get_graph

_MAX_DEPTH = 10


def _clamp_depth(depth: int) -> int:
    return max(1, min(depth, _MAX_DEPTH))


def impact_of(symbol: str, group_id: str, depth: int = 3) -> list[dict]:
    """
    Return all CodeChunks reachable from *symbol* via outgoing CALLS edges
    within *depth* hops.  These are the symbols that may be affected by
    a change to *symbol*.

    Results are ordered by hop distance (closest first).
    """
    d = _clamp_depth(depth)
    g = get_graph(group_id)

    # FalkorDB supports variable-length patterns: -[:CALLS*1..N]->
    result = g.query(
        f"""
        MATCH (src:CodeChunk)
        WHERE (src.symbol = $sym OR src.symbol ENDS WITH $dotsym)
          AND src.group_id = $gid
          AND src.valid = true
        WITH src
        MATCH (src)-[:CALLS*1..{d}]->(target:CodeChunk)
        WHERE target.group_id = $gid AND target.valid = true
        RETURN DISTINCT
            target.id        AS id,
            target.symbol    AS symbol,
            target.path      AS path,
            target.kind      AS kind,
            target.signature AS signature,
            target.start_line AS start_line,
            target.end_line  AS end_line
        LIMIT 200
        """,
        {"sym": symbol, "dotsym": f".{symbol}", "gid": group_id},
    )

    return [
        {
            "id":         row[0],
            "symbol":     row[1],
            "path":       row[2],
            "kind":       row[3],
            "signature":  row[4],
            "start_line": row[5],
            "end_line":   row[6],
        }
        for row in result.result_set
    ]


def callers_of(symbol: str, group_id: str, depth: int = 1) -> list[dict]:
    """
    Return all CodeChunks that call *symbol*, up to *depth* hops upstream.
    depth=1 returns direct callers only (default and most useful).
    """
    d = _clamp_depth(depth)
    g = get_graph(group_id)

    result = g.query(
        f"""
        MATCH (tgt:CodeChunk)
        WHERE (tgt.symbol = $sym OR tgt.symbol ENDS WITH $dotsym)
          AND tgt.group_id = $gid
          AND tgt.valid = true
        WITH tgt
        MATCH (caller:CodeChunk)-[:CALLS*1..{d}]->(tgt)
        WHERE caller.group_id = $gid AND caller.valid = true
        RETURN DISTINCT
            caller.id        AS id,
            caller.symbol    AS symbol,
            caller.path      AS path,
            caller.kind      AS kind,
            caller.signature AS signature,
            caller.start_line AS start_line,
            caller.end_line  AS end_line
        LIMIT 200
        """,
        {"sym": symbol, "dotsym": f".{symbol}", "gid": group_id},
    )

    return [
        {
            "id":         row[0],
            "symbol":     row[1],
            "path":       row[2],
            "kind":       row[3],
            "signature":  row[4],
            "start_line": row[5],
            "end_line":   row[6],
        }
        for row in result.result_set
    ]


def imports_of(file: str, group_id: str) -> list[dict]:
    """
    Return the list of files directly imported by *file*.
    Uses IMPORTS edges between FileNode nodes.
    """
    g = get_graph(group_id)

    result = g.query(
        """
        MATCH (src:FileNode {path: $path, group_id: $gid})-[:IMPORTS]->(tgt:FileNode)
        RETURN tgt.path AS path, tgt.ext AS ext
        ORDER BY tgt.path
        LIMIT 500
        """,
        {"path": file, "gid": group_id},
    )

    return [{"path": row[0], "ext": row[1]} for row in result.result_set]


def imported_by(file: str, group_id: str) -> list[dict]:
    """
    Return the list of files that import *file* (reverse of imports_of).
    Useful for impact analysis at the file level.
    """
    g = get_graph(group_id)

    result = g.query(
        """
        MATCH (src:FileNode)-[:IMPORTS]->(tgt:FileNode {path: $path, group_id: $gid})
        RETURN src.path AS path, src.ext AS ext
        ORDER BY src.path
        LIMIT 500
        """,
        {"path": file, "gid": group_id},
    )

    return [{"path": row[0], "ext": row[1]} for row in result.result_set]
