"""
MCP memory server — FastMCP mounted on FastAPI, port 7333.

Endpoints
─────────
GET  /health           liveness probe
GET  /status/{gid}     ingest progress
POST /ingest           trigger bulk ingest (SessionStart hook)
POST /reindex          re-index one file  (PostToolUse hook)
GET  /mcp/sse          MCP SSE stream (Claude Code)
POST /mcp/messages/    MCP message pairing (SSE transport)
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from .config import config
from .ingestion import ingest_repo, reindex_file
from .tools.code_fetch import code_fetch as _code_fetch
from .tools.code_search import code_search as _code_search
from .tools.memory_search import memory_query as _memory_query
from .tools.memory_search import memory_search as _memory_search
from .tools.memory_write import memory_add as _memory_add
from .tools.memory_write import memory_extend as _memory_extend
from .tools.memory_write import memory_immunize as _memory_immunize
from .tools.memory_write import memory_release as _memory_release
from .tools.graph_tools import (
    impact_of as _impact_of,
    callers_of as _callers_of,
    imports_of as _imports_of,
    imported_by as _imported_by,
)

log = logging.getLogger(__name__)

_ingest_status: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# FastMCP — tool definitions
# ---------------------------------------------------------------------------

mcp = FastMCP("memory")


@mcp.tool()
async def code_search(query: str, group_id: str, k: int = 10) -> list[dict]:
    """Search the code index by semantic + keyword similarity. Returns ranked chunks with path, symbol, signature, and line range."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _code_search, query, group_id, k)


@mcp.tool()
async def code_fetch(group_id: str, node_id: str = "", path: str = "", symbol: str = "") -> dict:
    """Fetch the exact source of a code chunk by node_id or path+symbol."""
    return _code_fetch(
        node_id=node_id or None,
        path=path or None,
        symbol=symbol or None,
        group_id=group_id,
    )


@mcp.tool()
async def memory_search(query: str, group_id: str, k: int = 10) -> list[dict]:
    """Search episodic memory (facts, decisions, conventions) by semantic + keyword similarity."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _memory_search, query, group_id, k)


@mcp.tool()
async def memory_query(query: str, group_id: str, symbol: str = "") -> list[dict]:
    """Targeted memory lookup, optionally filtered to facts anchored to a code symbol."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _memory_query, query, group_id, symbol or None)


@mcp.tool()
async def memory_immunize(id: str, group_id: str) -> dict:
    """Mark a memory fact as immune — never auto-purged or invalidated."""
    return _memory_immunize(id, group_id)


@mcp.tool()
async def memory_release(id: str, group_id: str) -> dict:
    """Remove immunity from a memory fact — subject to 30-day retention again."""
    return _memory_release(id, group_id)


@mcp.tool()
async def memory_extend(id: str, group_id: str, days: int) -> dict:
    """Push back the expiry of a memory fact by N days without making it immune."""
    return _memory_extend(id, group_id, days)


@mcp.tool()
async def memory_add(
    content: str,
    group_id: str,
    type: str = "fact",
    anchor: str = "",
    valid_from: int = 0,
) -> dict:
    """[haiku only] Persist an episodic fact. Dedup-checked before insert."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        _memory_add,
        content,
        group_id,
        type,
        anchor or None,
        valid_from or None,
    )


# ---------------------------------------------------------------------------
# Phase 5B — call graph tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def impact_of(symbol: str, group_id: str, depth: int = 3) -> list[dict]:
    """Return CodeChunks reachable via CALLS edges from *symbol* (up to *depth* hops).
    Use this to find what code may be affected by a change to a given function."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _impact_of, symbol, group_id, depth)


@mcp.tool()
async def callers_of(symbol: str, group_id: str, depth: int = 1) -> list[dict]:
    """Return CodeChunks that call *symbol*, up to *depth* hops upstream.
    depth=1 returns direct callers only."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _callers_of, symbol, group_id, depth)


@mcp.tool()
async def imports_of(file: str, group_id: str) -> list[dict]:
    """Return files directly imported by *file* (IMPORTS edges from FileNode)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _imports_of, file, group_id)


@mcp.tool()
async def imported_by(file: str, group_id: str) -> list[dict]:
    """Return files that import *file* (reverse IMPORTS traversal)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _imported_by, file, group_id)


# ---------------------------------------------------------------------------
# FastAPI app — control plane + health + MCP mount
# ---------------------------------------------------------------------------

async def _warm_models_background() -> None:
    """Download and cache embedding models on startup (blocking download, non-blocking for the server)."""
    from .embedder import ensure_models

    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, ensure_models)
        log.info("embedding models ready")
    except Exception as exc:
        log.warning("model warm-up failed (will retry on first embed call): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.create_task(_warm_models_background())
    yield


app = FastAPI(title="memory-mcp", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


class IngestRequest(BaseModel):
    group_id: str
    repo_path: str


class ReindexRequest(BaseModel):
    group_id: str
    file_path: str


class BuildGraphRequest(BaseModel):
    group_id: str
    repo_path: str


@app.post("/build-graph")
async def trigger_build_graph(req: BuildGraphRequest):
    """Non-blocking: (re)build the call graph for a project."""
    from .graph_builder import build_graph

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(None, build_graph, req.group_id, req.repo_path)
            log.info("build-graph complete: %s", result)
        except Exception as exc:
            log.exception("build-graph failed for %s", req.group_id)

    asyncio.create_task(_run())
    return {"status": "started", "group_id": req.group_id}


@app.get("/graph-status/{group_id}")
def graph_status(group_id: str):
    """Return counts of FileNodes, CALLS edges, and IMPORTS edges for a project."""
    from .db import get_graph as _get_graph
    g = _get_graph(group_id)
    try:
        fn  = g.query("MATCH (f:FileNode {group_id: $gid}) RETURN count(f)", {"gid": group_id}).result_set[0][0]
        ca  = g.query("MATCH (:CodeChunk)-[r:CALLS]->(:CodeChunk) RETURN count(r)").result_set[0][0]
        im  = g.query("MATCH (:FileNode)-[r:IMPORTS]->(:FileNode) RETURN count(r)").result_set[0][0]
        return {"group_id": group_id, "file_nodes": fn, "calls_edges": ca, "imports_edges": im}
    except Exception as exc:
        return {"group_id": group_id, "error": str(exc)}


@app.post("/ingest")
async def trigger_ingest(req: IngestRequest):
    """Non-blocking: launches ingest as a background task."""
    gid = req.group_id
    if _ingest_status.get(gid, {}).get("status") == "running":
        return {"status": "already_running", "group_id": gid}

    _ingest_status[gid] = {"status": "running", "group_id": gid}

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(None, ingest_repo, gid, req.repo_path)
            _ingest_status[gid] = {"status": "done", "group_id": gid, **result}
        except Exception as exc:
            log.exception("ingest failed for %s", gid)
            _ingest_status[gid] = {"status": "error", "group_id": gid, "error": str(exc)}

    asyncio.create_task(_run())
    return {"status": "started", "group_id": gid}


@app.post("/reindex")
async def trigger_reindex(req: ReindexRequest):
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, reindex_file, req.group_id, req.file_path)
    return {"status": "ok", **result}


@app.get("/status/{group_id}")
def ingest_status(group_id: str):
    return _ingest_status.get(group_id, {"status": "unknown", "group_id": group_id})



# Mount MCP SSE under /mcp — Claude Code connects to http://host:7333/mcp/sse
app.mount("/mcp", mcp.sse_app())


if __name__ == "__main__":
    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=config.SERVER_PORT,
        log_level="info",
    )
