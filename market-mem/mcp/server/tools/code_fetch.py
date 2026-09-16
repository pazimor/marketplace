"""
Fetch the exact source slice for a CodeChunk node.
Code is stored by reference (path + line range) — never in the DB.
"""
from __future__ import annotations

from pathlib import Path

from ..db import get_graph
from ..paths import indexed_commit, resolve


def code_fetch(node_id: str | None = None,
               path: str | None = None,
               symbol: str | None = None,
               group_id: str | None = None) -> dict:
    """
    Fetch source for a chunk identified by node_id OR (path + symbol).

    *path* is repo-relative, exactly as code_search returns it.

    Returns {path, symbol, start_line, end_line, source, indexed_commit} or
    {error}. ``source`` is None with ``reason: "source_unavailable"`` when the
    chunk is indexed but the file isn't readable on this server.
    """
    if node_id and group_id:
        g = get_graph(group_id)
        result = g.query(
            "MATCH (c:CodeChunk {id: $id}) RETURN c.path, c.symbol, c.start_line, c.end_line",
            {"id": node_id},
        )
        if not result.result_set:
            return {"error": f"chunk {node_id!r} not found"}
        file_path, sym, sl, el = result.result_set[0]
    elif path and symbol and group_id:
        import hashlib
        cid = hashlib.sha256(f"{path}::{symbol}".encode()).hexdigest()[:32]
        g = get_graph(group_id)
        result = g.query(
            "MATCH (c:CodeChunk {id: $id}) RETURN c.path, c.symbol, c.start_line, c.end_line",
            {"id": cid},
        )
        if not result.result_set:
            return {"error": f"symbol {symbol!r} not found in {path!r}"}
        file_path, sym, sl, el = result.result_set[0]
    else:
        return {"error": "provide node_id+group_id or path+symbol+group_id"}

    # Stored paths are repo-relative; the source lives either in a working tree
    # on this machine or in the server's git mirror (see paths.resolve).
    abs_path = resolve(group_id, file_path)
    commit = indexed_commit(group_id)

    if abs_path is None:
        # The chunk is indexed but its source isn't readable here — typically a
        # client working off a machine whose files the server never sees. Return
        # the coordinates so the caller can read the file itself, rather than a
        # bare error it can do nothing with.
        return {
            "path": file_path,
            "symbol": sym,
            "start_line": int(sl),
            "end_line": int(el),
            "source": None,
            "reason": "source_unavailable",
            "detail": ("this server cannot read the file; read it locally at the "
                       "path and line range above"),
            "indexed_commit": commit,
        }

    try:
        lines = Path(abs_path).read_text(errors="replace").splitlines()
        # start_line / end_line are 1-based
        sl = max(1, int(sl))
        el = min(len(lines), int(el))
        source = "\n".join(lines[sl - 1 : el])

        if group_id:
            from .stats import record_fetch
            record_fetch(group_id, abs_path, len(source))

        return {
            "path": file_path,
            "symbol": sym,
            "start_line": sl,
            "end_line": el,
            "source": source,
            "indexed_commit": commit,
        }
    except FileNotFoundError:
        return {"error": f"file not found: {file_path}"}
