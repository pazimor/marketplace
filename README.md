<div align="center">
  <img src="assets/marketplace.png" width="100" alt="marketplace logo"/>

  # marketplace

  **A Claude Code plugin marketplace: give your agent a memory and a map of your codebase.**

  [![CLI](https://img.shields.io/badge/CLI-market-informational)](#quickstart)
  [![Python](https://img.shields.io/badge/python-%E2%89%A53.11-blue)](#quickstart)
  [![Docker](https://img.shields.io/badge/runtime-Docker-2496ED?logo=docker&logoColor=white)](#architecture)

</div>

---

Claude Code forgets everything between sessions and has no map of your repo beyond what fits in a grep. **marketplace** ships a single plugin, `memory`, that fixes both — a semantic index of your code and a durable, self-curating memory of past sessions, both served locally through one MCP endpoint.

## Why

Most "AI memory" layers re-run an LLM over every episode to decide what's worth keeping — fine for a demo, expensive and slow at the scale of a real codebase touched every day. `memory` splits the problem into three mechanisms instead:

- **Code index** — bulk-ingested with embeddings only, **zero LLM calls**. Every function in your repo becomes a searchable, referenceable chunk.
- **Episodic memory** — written once per past session, not per turn: a cheap model (haiku) extracts candidate facts from the transcript, a stronger one (sonnet) arbitrates merges/conflicts against what's already known. You pay the LLM cost once, asynchronously, well after the work is done.
- **Roadmap ↔ code traceability** — every task the agent implements gets a `PRODUCED` edge to the exact code symbols it wrote (`task_link_code`). The roadmap isn't a markdown file that drifts from reality: it's a graph node with a live pointer to its implementation. That pays off the moment a decision needs revisiting — `roadmap_impact` on a spec or task returns `produced_code`, the precise set of functions to re-inspect, instead of re-discovering scope by grepping the repo again.

Together, these mean the agent reasons over "what the code is", "what we learned about it", and "what decision produced it" side by side, in the same graph, through the same MCP server.

## What's inside

| Layer | Written by | Cost | Retention |
|---|---|---|---|
| **Code index** (`:CodeChunk`) | AST parse (tree-sitter) → embed, at session start + incrementally on edits | Zero LLM | Kept in sync with the repo |
| **Episodic memory** (`:MemoryEpisode`) | Distiller: haiku extractor → sonnet arbiter, over past transcripts | 2 small LLM calls, once per session | 30-day validity + 30-day grace, or permanent (`preference`/`workflow` facts, or `immune`) |
| **Roadmap graph** (specs, milestones, tasks) | `roadmapper` agent: `roadmap_apply` for structure, `task_link_code` for `PRODUCED` edges once a task ships | Zero LLM to query (`roadmap_impact`, `backlog`); LLM only when planning/re-planning | Canon — superseded nodes are marked `obsolete`, never silently deleted |

A set of **agents** (`orchestrator`, `worker`, `worker-small`, `roadmapper`) plans and executes backlog-driven work against that graph: the orchestrator dispatches scoped tasks, workers implement and report back the symbols they touched, and the roadmapper links them to the task and re-runs impact analysis on anything downstream.

## Architecture

Everything runs in one small Docker stack, shared across every project on the machine — never one stack per repo.

```
 Claude Code (hooks, agents)
        │  HTTPS/SSE → 127.0.0.1:<MEM_PORT>
        ▼
┌── docker network "mem-net" ─────────────────────────────┐
│                                                          │
│   mcp        MCP server + embedding + ingestion          │
│              (only service exposed, TLS on localhost)    │
│                        │                                 │
│   falkordb   vectors + graph + full-text                 │
│              (internal only, one graph per project)      │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

- **`mcp`** does its own embedding (code + memory models loaded and cached in-container) — no separate embedding service to run or babysit.
- **`falkordb`** holds one named graph per project (`g_<hash-of-remote-or-path>`), combining vector search, full-text (RediSearch) and graph edges in a single store.
- Retrieval is hybrid (semantic + lexical, RRF-fused) and costs **zero LLM calls** at query time.

## MCP tools

Exposed to the agent (read + safe writes):

| Tool | Layer | Purpose |
|---|---|---|
| `code_search` | Code | Semantic + lexical search over indexed symbols |
| `code_fetch` | Code | Fetch the exact referenced slice of a symbol |
| `memory_search` | Episodic | Hybrid search over past-session facts |
| `memory_query` | Episodic | Targeted lookup, filterable by anchored symbol |
| `memory_immunize` / `memory_release` / `memory_extend` | Episodic | Protect, unprotect, or extend a fact's retention |
| `backlog`, `roadmap_apply`, `task_claim`, `roadmap_lint` | Roadmap | Plan and drive backlog work against the graph |
| `task_link_code` | Roadmap↔Code | Record the `PRODUCED` edge from a finished task to the code symbols it wrote |
| `roadmap_impact` | Roadmap↔Code | Given a changed spec/task, return every downstream node **and** its `produced_code` — what to re-inspect before re-deciding |

Writes to the code/memory graph itself (`memory_add`, `code_add`, …) are reserved for the distiller and internal tooling — the interactive agent never writes memory directly.

## Quickstart

**Requirements:** Python ≥ 3.11, Docker (with `docker compose`), Claude Code.

```bash
# 1. Install the CLI
pip install -e .

# 2. Configure (defaults work out of the box on macOS/Linux)
cp .env.example .env

# 3. Install the plugin — starts the Docker stack, registers hooks
market install --target claude --scope user

# 4. Restart Claude Code, then check everything is healthy
market doctor
```

```bash
market status                                    # ingestion state for the current repo
market ingest --repo-path /path/to/repo          # force a manual re-index
market uninstall --target claude --scope user    # reversible, reads the install manifest
```

## Usage

Once installed, the agent calls the MCP tools on its own — you don't invoke them by hand. A typical turn looks like:

```
> "Where do we validate the roadmap DoD before closing a task?"

  code_search("validate roadmap DoD before task close")
    → task_verify.py:42  validate_definition_of_done()

  memory_search("roadmap DoD gate decisions")
    → "DoD validation is deterministic per task type (feature/bug/doc/test/infra);
       run it before every task_release(done=true)." — recorded 2026-06-14
```

The agent reads code by reference (never a stale copy) and cross-checks it against what past sessions already decided — no re-explaining context you've already given it.

## Repo layout

```
marketplace/
├── .claude-plugin/marketplace.json   # plugin catalogue
├── plugins/memory/                   # the plugin — hooks, agents, skills, MCP config
│   ├── hooks/                        # session_start, post_tool_use, subagent_stop, session_end
│   │   └── prompts/                  # extractor.md / arbiter.md — distiller prompts, kept out of Python
│   ├── agents/                       # orchestrator, worker, worker-small, roadmapper
│   └── skills/                       # graph-usage, roadmap-maker, task-verify, retro
├── installer/                        # `market` CLI (install / uninstall / status / doctor)
└── market-mem/                       # Docker stack: FalkorDB + MCP server
```

See [`market-mem/README.md`](market-mem/README.md) for environment variables and stack internals.

## Status

The project ships incrementally by phase — code indexing and read tools are usable daily today; the roadmap/agent layer is active and evolving.

| Phase | Scope | Status |
|---|---|---|
| 0 | Docker scaffold (FalkorDB + MCP) | ✅ |
| 1 | Bulk code ingestion + code RAG + read tools | ✅ |
| 2 | Episodic layer (distiller: haiku → sonnet) | ✅ |
| 3 | Installer CLI | ✅ |
| 4 | ~~Codex adapter~~ | ❌ dropped — episodic writes need haiku via the Claude Code account |
| 5 | Code↔memory graph coupling | 🚧 data-driven, only if anchor quality warrants it |
