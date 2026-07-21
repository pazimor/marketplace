"""
MCP memory server — FastMCP mounted on FastAPI, port 7333.

Endpoints
─────────
GET  /health           liveness probe
GET  /status/{gid}     ingest progress
GET  /bootstrap/{gid}  session bootstrap (backlog + memories + stats)
GET  /mcp-stats        per-route MCP usage (persisted to .mcp_memory)
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
from .tools.memory_write import memory_delete as _memory_delete
from .tools.memory_write import memory_extend as _memory_extend
from .tools.memory_write import memory_immunize as _memory_immunize
from .tools.memory_write import memory_release as _memory_release
from .tools.graph_tools import (
    impact_of as _impact_of,
    callers_of as _callers_of,
    imports_of as _imports_of,
    imported_by as _imported_by,
)
from .tools.overview import bootstrap as _bootstrap
from .tools.sessions import session_mark_processed as _session_mark_processed
from .tools.sessions import sessions_processed as _sessions_processed
from .tools.overview import graph_overview as _graph_overview
from .tools.route_stats import record_query as _record_query
from .tools.route_stats import summary as _route_summary
from .tools.route_stats import track as _track_route
from .tools.roadmap import (
    backlog_get as _backlog_get,
    roadmap_apply as _roadmap_apply,
    roadmap_export as _roadmap_export,
    roadmap_impact as _roadmap_impact,
    roadmap_lint as _roadmap_lint,
    task_claim as _task_claim,
    task_link_code as _task_link_code,
    task_release as _task_release,
)

log = logging.getLogger(__name__)

_ingest_status: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# FastMCP — tool definitions
# ---------------------------------------------------------------------------

mcp = FastMCP("memory")


def _known_graphs() -> list[dict]:
    """Project graphs known to this server: {group_id, repo_path}.

    Used to make a missing group_id fail helpfully instead of opaquely."""
    from .db import get_client, get_graph

    out: list[dict] = []
    try:
        for name in get_client().list_graphs():
            if not name.startswith("g_") or name.startswith("g_it_"):
                continue
            gid = name[2:]
            repo = None
            try:
                rs = get_graph(gid).query(
                    "MATCH (p:Project {group_id: $gid}) RETURN p.repo_path LIMIT 1",
                    {"gid": gid},
                ).result_set
                repo = rs[0][0] if rs else None
            except Exception:
                pass
            out.append({"group_id": gid, "repo_path": repo})
    except Exception as exc:
        log.debug("known_graphs failed: %s", exc)
    return out


def _missing_gid() -> dict:
    return {
        "error": "group_id is required (it partitions projects — one graph per repo).",
        "hint": ("Your project's group_id is printed in the 'Project graph' block "
                 "injected at session start (Identity line). Pick the graph whose "
                 "repo_path matches your working directory."),
        "known_graphs": _known_graphs(),
    }


def tracked_tool(*args, **kwargs):
    """`@mcp.tool()` + a per-route usage counter persisted to `.mcp_memory`.

    Wraps the tool so every invocation is recorded (see tools/route_stats.py)
    without touching the tool body or its generated schema."""
    decorate = mcp.tool(*args, **kwargs)

    def wrap(func):
        return decorate(_track_route(func))

    return wrap


@tracked_tool()
async def code_search(query: str, group_id: str = "", k: int = 10) -> dict:
    """Call this when you look for a CONCEPT and don't know the exact symbol
    name ("where is retry handled?", "what validates payments?"). Complements
    Grep — Grep stays better for literal/exhaustive sweeps of a known string.
    Each hit includes a snippet, so you can judge relevance without a follow-up
    fetch (~10-20x fewer tokens than a full Read). An empty result is cheap —
    call speculatively at the start of exploration. group_id: see the
    'Project graph' session block."""
    if not group_id:
        return _missing_gid()
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, _code_search, query, group_id, k)
    _record_query("code_search", query, len(res.get("results", [])))
    return res


@tracked_tool()
async def code_fetch(group_id: str = "", node_id: str = "", path: str = "", symbol: str = "") -> dict:
    """Fetch the exact source of one chunk found via code_search (by node_id,
    or path+symbol). Use this instead of Read when the chunk is enough —
    Read only when you need the surrounding file (e.g. to Edit)."""
    if not group_id:
        return _missing_gid()
    return _code_fetch(
        node_id=node_id or None,
        path=path or None,
        symbol=symbol or None,
        group_id=group_id,
    )


@tracked_tool()
async def memory_search(query: str, group_id: str = "", k: int = 10) -> dict:
    """Call this BEFORE choosing an approach, refactoring, or contradicting an
    existing choice — past decisions, conventions and facts live here and can
    invalidate your plan. Also when the user references shared history ("comme
    on avait dit", "le bug d'avant"). An empty result is cheap and fine —
    call speculatively by default at task start."""
    if not group_id:
        return _missing_gid()
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, _memory_search, query, group_id, k)
    _record_query("memory_search", query, len(res.get("results", [])))
    return res


@tracked_tool()
async def memory_query(query: str, group_id: str = "", symbol: str = "") -> list[dict]:
    """Targeted memory lookup filtered to facts anchored to one code symbol —
    use when you already know WHICH function/module you're touching and want
    only the decisions attached to it (memory_search for the broad version)."""
    if not group_id:
        return [_missing_gid()]
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _memory_query, query, group_id, symbol or None)


@tracked_tool()
async def memory_immunize(id: str, group_id: str) -> dict:
    """Mark a memory fact as immune — never auto-purged or invalidated."""
    return _memory_immunize(id, group_id)


@tracked_tool()
async def memory_release(id: str, group_id: str) -> dict:
    """Remove immunity from a memory fact — subject to 30-day retention again."""
    return _memory_release(id, group_id)


@tracked_tool()
async def memory_extend(id: str, group_id: str, days: int) -> dict:
    """Push back the expiry of a memory fact by N days without making it immune."""
    return _memory_extend(id, group_id, days)


@tracked_tool()
async def memory_add(
    content: str,
    group_id: str,
    type: str = "fact",
    anchor: str = "",
    valid_from: int = 0,
    kind: str = "episodic",
) -> dict:
    """[distiller only] Persist a fact. Dedup-checked before insert.
    kind: 'episodic' (30-day retention) | 'preference' | 'workflow'
    (user habits/conventions — exempt from time-based purge)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: _memory_add(
            content,
            group_id,
            type,
            anchor or None,
            valid_from or None,
            kind=kind,
            source="distiller",
        ),
    )


@tracked_tool()
async def memory_delete(id: str, group_id: str) -> dict:
    """[distiller only] Hard-delete one fact — used when merging duplicates
    or retracting a fact contradicted by newer evidence."""
    return _memory_delete(id, group_id)


# ---------------------------------------------------------------------------
# Roadmap layer — structured nodes, deterministic lint, task claims
# ---------------------------------------------------------------------------

@tracked_tool()
async def graph_overview(group_id: str = "") -> dict:
    """Orient yourself in the project graph in ONE call: node counts by type
    (code / memory / roadmap), 5 latest memories, active milestones with
    progress, and currently claimed tasks. Call this at the start of a task
    instead of exploring the repo manually."""
    if not group_id:
        return _missing_gid()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _graph_overview, group_id)


@tracked_tool()
async def roadmap_apply(group_id: str, ops: list[dict], author: str = "", worktree: str = "") -> dict:
    """Apply a STRUCTURED roadmap patch (never rewrite documents). Ops:
    {"op":"create","kind":"spec|milestone|task|canon","fields":{"title":...,"description":...,"status":...,"type":...,"dod":...,"due":...}} |
    {"op":"update","id":"ROADMAP:TASK:3","fields":{...}} (field-by-field merge) |
    {"op":"delete","id":...} |
    {"op":"link","type":"DEPENDS_ON|IMPLEMENTS|PART_OF|DETAILS","from":id,"to":id} |
    {"op":"unlink",...}.
    'canon' nodes carry implementation detail (Canon Driven Development) and
    DETAILS-link to a task or spec; task_claim bundles them for dispatch.
    Returns per-op results + a deterministic lint report. Claims are NOT
    editable here — use task_claim/task_release."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _roadmap_apply, group_id, ops, author, worktree)


@tracked_tool()
async def roadmap_lint(group_id: str) -> dict:
    """Deterministic roadmap validation: schema (status enums, titles),
    cross-references, orphan milestones, circular DEPENDS_ON. Run after any
    roadmap change; fix errors before continuing. No LLM re-read needed."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _roadmap_lint, group_id)


@tracked_tool()
async def task_claim(task_id: str, group_id: str, user: str, worktree: str = "") -> dict:
    """Claim a task before working on it (multi-worktree safety). REFUSES if
    another user/worktree already holds it — pick another task in that case.
    Claiming a 'todo' task moves it to 'in_progress'. The result includes the
    dispatch-ready CDD bundle: task fields (title/description/type/dod/due),
    attached canon nodes, and depends_on."""
    return _task_claim(task_id, group_id, user, worktree)


@tracked_tool()
async def task_release(task_id: str, group_id: str, user: str, done: bool = False) -> dict:
    """Release a claimed task. done=true marks it done (only after its
    Definition of Done is verified — see the task-verify skill); done=false
    puts it back to 'todo'."""
    return _task_release(task_id, group_id, user, done)


@tracked_tool()
async def task_link_code(task_id: str, group_id: str, symbols: list[str]) -> dict:
    """AFTER a task is done: link it to the code it produced
    ((:Task)-[:PRODUCED]->(:CodeChunk)) from the symbols reported by the
    worker (module.func). Symbols absent from the code index are returned in
    `missing` — retry them after the next reindex."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _task_link_code, task_id, group_id, symbols)


@tracked_tool()
async def backlog(group_id: str, include_done: bool = False) -> dict:
    """Persistent backlog: tasks grouped by status (todo / in_progress /
    blocked / done) with claims, milestones and dependencies. Call this to
    resume exactly where the previous session stopped."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _backlog_get, group_id, include_done)


@tracked_tool()
async def roadmap_impact(node_id: str, group_id: str) -> dict:
    """BEFORE changing a spec or task: what does it affect? Returns
    implementing tasks and transitive dependents via graph traversal
    (Cypher), not a document re-read."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _roadmap_impact, node_id, group_id)


@tracked_tool()
async def roadmap_export(group_id: str) -> str:
    """Generate the roadmap markdown from the graph (deterministic). The
    graph is the source of truth; never edit the generated markdown by hand."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _roadmap_export, group_id)


# ---------------------------------------------------------------------------
# Phase 5B — call graph tools
# ---------------------------------------------------------------------------

@tracked_tool()
async def impact_of(symbol: str, group_id: str = "", depth: int = 3) -> list[dict]:
    """BEFORE changing a function: what code may be affected? Returns
    CodeChunks reachable via CALLS edges from *symbol* (up to *depth* hops) —
    graph traversal, no manual exploration needed."""
    if not group_id:
        return [_missing_gid()]
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _impact_of, symbol, group_id, depth)


@tracked_tool()
async def callers_of(symbol: str, group_id: str = "", depth: int = 1) -> list[dict]:
    """Who calls *symbol*? Use instead of a manual Grep for call sites.
    Returns CodeChunks up to *depth* hops upstream (depth=1 = direct callers)."""
    if not group_id:
        return [_missing_gid()]
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _callers_of, symbol, group_id, depth)


@tracked_tool()
async def imports_of(file: str, group_id: str = "") -> list[dict]:
    """Return files directly imported by *file* (IMPORTS edges from FileNode)."""
    if not group_id:
        return [_missing_gid()]
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _imports_of, file, group_id)


@tracked_tool()
async def imported_by(file: str, group_id: str = "") -> list[dict]:
    """Return files that import *file* (reverse IMPORTS traversal)."""
    if not group_id:
        return [_missing_gid()]
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


@app.get("/stats/{group_id}")
def token_stats(group_id: str):
    """Cumulative token-savings estimate for the code RAG (see tools/stats.py)."""
    from .tools.stats import stats_get
    try:
        return stats_get(group_id)
    except Exception as exc:
        return {"group_id": group_id, "error": str(exc)}


@app.get("/mcp-stats")
def mcp_route_stats():
    """Per-route MCP usage: how many routes exist, how many are used, and the
    per-route call counts. Persisted to `.mcp_memory` (see tools/route_stats.py)."""
    try:
        return _route_summary()
    except Exception as exc:
        return {"error": str(exc)}


class SessionProcessedRequest(BaseModel):
    group_id: str
    session_id: str
    status: str = "done"
    facts_written: int = 0


@app.get("/sessions/{group_id}")
async def processed_sessions(group_id: str):
    """Distillation ledger: which session transcripts were already processed."""
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _sessions_processed, group_id)
    except Exception as exc:
        return {"error": str(exc), "group_id": group_id}


@app.post("/sessions/processed")
async def mark_session_processed(req: SessionProcessedRequest):
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(
            None, _session_mark_processed,
            req.group_id, req.session_id, req.status, req.facts_written,
        )
    except Exception as exc:
        return {"error": str(exc), "group_id": req.group_id}


@app.get("/bootstrap/{group_id}")
async def session_bootstrap(group_id: str):
    """Session bootstrap for the SessionStart hook: backlog + recent memories
    + graph stats. Deterministic, no embedding call."""
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _bootstrap, group_id)
    except Exception as exc:
        return {"error": str(exc), "group_id": group_id}



# Mount MCP SSE under /mcp — Claude Code connects to http://host:7333/mcp/sse
app.mount("/mcp", mcp.sse_app())


if __name__ == "__main__":
    import os

    # Optional TLS: if cert + key are provided (mounted into the container),
    # serve https. Falls back to plain http when unset (backward compatible).
    ssl_kwargs = {}
    cert = os.getenv("TLS_CERT_FILE")
    key = os.getenv("TLS_KEY_FILE")
    if cert and key and os.path.exists(cert) and os.path.exists(key):
        ssl_kwargs = {"ssl_certfile": cert, "ssl_keyfile": key}

    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=config.SERVER_PORT,
        log_level="info",
        **ssl_kwargs,
    )
