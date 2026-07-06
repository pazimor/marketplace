# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A **Claude Code plugin marketplace** ("ECC"-style) that distributes:
- **Skills and agents** for Claude Code
- A **proprietary memory system** — a local RAG layer combining code indexing (bulk, zero-LLM) with episodic memory (written by haiku at session end)

The repo is currently in the design/planning phase. `ROADMAP.md` and `DB_SCHEMA.md` are the authoritative specs; no code has been written yet.

## Architecture overview

### Plugin layout (target structure)
```
marketplace/
├── .claude-plugin/marketplace.json   # plugin catalogue (ONE plugin: memory)
├── plugins/
│   └── memory/                       # the single plugin — everything ships together
│       ├── .claude-plugin/plugin.json
│       ├── hooks/                    # session_start (docker+ingest+distiller), bootstrap (context injection), post_tool_use, subagent_stop, session_end
│       │   ├── prompts/              # extractor.md / arbiter.md (distiller prompts)
│       │   └── tests/                # offline distiller tests + real-token smoke script
│       ├── agents/                   # orchestrator, worker, worker-small, roadmapper
│       ├── skills/                   # graph-usage, roadmap-maker, task-verify, retro
│       └── .mcp.json
├── installer/                        # CLI: install/uninstall/status/doctor
└── market-mem/                       # shared FalkorDB + MCP server (Docker)
```

### Infrastructure (Docker)
One shared Docker stack per machine, never one-per-project:
- **FalkorDB** — vector + full-text + graph DB; one named graph per project (`g_<hash>`)
- **Ollama** — local embedding, stateless, not published on host network
- **MCP server** — containerized, exposes endpoint on `127.0.0.1` only (SSE/HTTP)

All three are on an internal Docker network (`mem_net`). Hooks on the host talk only to the MCP endpoint, never to FalkorDB or Ollama directly.

### Memory system — two layers in one FalkorDB graph
| Layer | Node label | How written | LLM cost |
|---|---|---|---|
| Code index | `:CodeChunk` | Bulk at `SessionStart`, AST → embed | Zero LLM |
| Episodic memory | `:MemoryEpisode` | Distiller at `SessionStart`: past transcripts → extractor (haiku) → arbiter (sonnet) | haiku + sonnet, once per past session |

**Distillation pipeline** (`plugins/memory/hooks/_distill.py`):
- Past session transcripts (`~/.claude/projects/<proj>/*.jsonl`) are distilled at the NEXT SessionStart — durable, replayable, captures crashed sessions
- Stage A extractor (haiku, `hooks/prompts/extractor.md`): transcript → candidate facts JSON, no writes
- Stage B arbiter (sonnet, `hooks/prompts/arbiter.md`): memory_search + decide ADD / MERGE / DISCARD via the MCP write tools — this is the dedup / contradiction gate
- Ledger `:ProcessedSession` in the graph (`GET /sessions/{gid}`, `POST /sessions/processed`) — idempotent; `failed` is retried, `done|skipped|empty` are final
- Background (detached process) by default; synchronous when `MEM_DISTILL_SYNC=1` or `distill_sync: true` in `~/.config/market/settings.json`
- Memory `kind`: `episodic` (30-day retention) vs `preference`/`workflow` (user habits — never time-purged; the arbiter only promotes them after recurrence)

**Key invariants:**
- Code is stored **by reference** (`path + [start_line, end_line]`), never copied into the DB
- `content_hash` gates re-embedding — only changed symbols are re-embedded
- Vector index uses `MAX_DIM = 2048` with zero-padding; switching embedding models = recompute, never index recreation
- Embedding models: `microsoft/graphcodebert-base` (code, 768d) and `nomic-ai/nomic-embed-text-v1.5` (memory, 768d)
- `group_id` = `hash(git remote URL)` (fallback: `hash(repo_path)`); one FalkorDB graph per project

### MCP tools
**Read (exposed to master):** `memory_search`, `memory_query`, `code_search`, `code_fetch`

**Safe writes (exposed to master):** `memory_immunize`, `memory_release`, `memory_extend`

**Hidden writes (distiller/debug only):** `memory_add`, `memory_delete`, `code_add`, `code_edit`, `code_delete`

### Hook design
| Hook | Action |
|---|---|
| `SessionStart` | `docker compose up` → health → bulk ingest (background) → distill past transcripts (background unless `MEM_DISTILL_SYNC=1`) |
| `PostToolUse (Write/Edit)` | Re-embed changed symbols (hash-gated) + session.log debug trail |
| `SubagentStop` | Code-RAG reconcile only (git diff → upsert changed symbols); no memory write |
| `SessionEnd` | Token-stats snapshot + session.log rotation; no LLM. The Docker stack stays up (shared across sessions — never stopped by hooks) |

There is **no Stop hook** anymore: episodic memory is written by the SessionStart distiller from the durable transcript, not at end of session.

### Retention policy
- Episodic facts (`kind: episodic`): invalidated after 30 days, hard-deleted after 30 days grace (60-day total window)
- `kind: preference` / `kind: workflow` facts are exempt from time-based purge (they describe the user, not the moment)
- `immune = true` exempts a fact from all purges; controlled via `memory_immunize`/`memory_release`/`memory_extend`

## Roadmap phases
- **Phase 0** — Docker scaffold (FalkorDB + Ollama + MCP server)
- **Phase 1** — Bulk code ingestion + code RAG + MCP read tools ← _usable daily from here_
- **Phase 2** — Episodic layer + haiku writer hook
- **Phase 3** — Installer CLI (install/uninstall/doctor, Claude Code scope)
- **Phase 4** — ~~Codex adapter~~ dropped (episodic writes require haiku through the Claude Code account; Codex cannot drive that)
- **Phase 5** — Code↔memory graph coupling (data-driven, only if anchor quality warrants it)

## Key decisions already made (do not re-open)
- Memory is a **proprietary layer**, not Graphiti (Graphiti's per-episode LLM calls make bulk ingestion too costly)
- Bulk ingestion = **zero LLM** (pure Ollama embedding)
- Master agent is **read-only**; all memory writes go through the distiller (extractor haiku → arbiter sonnet)
- Episodic memory is written at **SessionStart from past transcripts** (ledger-gated), not at Stop — the transcript on disk is the durable source
- Distiller prompts live in `plugins/memory/hooks/prompts/*.md` (extractor.md / arbiter.md), never inline in Python
- Orchestrator (worker / worker-small / roadmapper) is the entry point for **backlog-driven work only**, not for interactive sessions
- `SubagentStop` does **not** write episodic memory; it only reconciles code RAG
- Ollama runs **inside Docker** (`mem_net`), not reusing the host's Ollama instance
- Code chunking = **per function** (AST, tree-sitter); docstrings kept (signal for embedding quality)

## Open decisions (to resolve during implementation)
- `group_id` hashing: `git remote URL` preferred, `repo_path` fallback (needs confirmation)
- Whether to cache raw code content alongside the reference (currently: reference only, cache optional)
- Concurrency lock strategy for multi-session bulk ingest on the same repo
