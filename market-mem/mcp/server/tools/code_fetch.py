"""
Fetch the exact source slice for a CodeChunk node.
Code is stored by reference (path + line range) — never in the DB.
"""
from __future__ import annotations

from pathlib import Path

from ..db import get_graph


def code_fetch(node_id: str | None = None,
               path: str | None = None,
               symbol: str | None = None,
               group_id: str | None = None) -> dict:
    """
    Fetch source for a chunk identified by node_id OR (path + symbol).

    Returns {path, symbol, start_line, end_line, source} or {error}.
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

    try:
        lines = Path(file_path).read_text(errors="replace").splitlines()
        # start_line / end_line are 1-based
        sl = max(1, int(sl))
        el = min(len(lines), int(el))
        source = "\n".join(lines[sl - 1 : el])
        return {
            "path": file_path,
            "symbol": sym,
            "start_line": sl,
            "end_line": el,
            "source": source,
        }
    except FileNotFoundError:
        return {"error": f"file not found: {file_path}"}
