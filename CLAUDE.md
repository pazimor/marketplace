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
- **MCP server** — containerized, exposes endpoint on `127.0.0.1` only (SSE/HTTP); does its own embedding in-process (SentenceTransformers, models cached on a persistent volume) — no separate embedding service

Both are on an internal Docker network (`mem-net`). Hooks on the host talk only to the MCP endpoint, never to FalkorDB directly.

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
- Stored paths are **repo-relative**, and node ids derive from them (`sha256(rel_path::symbol)`) — two machines indexing the same repo must converge on the same nodes, never duplicate them. Absolute paths only ever exist in memory, while walking the filesystem
- `content_hash` gates re-embedding — only changed symbols are re-embedded
- A full ingest **owns the whole chunk set**: whatever it doesn't re-derive is swept (`seen_at` mark-and-sweep), mirroring the call graph's edge purge
- Vector index uses `MAX_DIM = 2048` with zero-padding; switching embedding models = recompute, never index recreation
- Embedding models: `microsoft/graphcodebert-base` (code, 768d) and `nomic-ai/nomic-embed-text-v1.5` (memory, 768d)
- `group_id` = `hash(git remote URL)` (fallback: `hash(repo_path)`); one FalkorDB graph per project

### MCP tools
**Read (exposed to master):** `memory_search`, `memory_query`, `code_search`, `code_fetch`

**Safe writes (exposed to master):** `memory_immunize`, `memory_release`, `memory_extend`

**Hidden writes (distiller/debug only):** `memory_add`, `memory_delete`, `code_add`, `code_edit`, `code_delete`

### Remote clients (one server, several machines)
The stack runs on one machine; other machines connect to it over the network.
- Auth: shared bearer token (`MEM_TOKEN`) on every route but `/health`. The server **refuses to start** unauthenticated when the port isn't loopback-bound
- `market install --expose` on the server, `market install --client-only` on the other machine (needs `MEM_HOST` + `MEM_TOKEN`, and the mkcert CA at `~/.config/market/ca.pem`)
- Memory and roadmap work unchanged — they never touch a path
- Code: the server can't read a remote client's files, so it indexes **its own git clone** (`POST /ingest {git_url}` → `/data/repos/<gid>`). The index tracks the last *pushed* commit, surfaced as `indexed_commit` on every read so stale answers are visible
- Unpushed edits still land via `POST /reindex {rel_path, content}`; the call graph waits for the next mirror ingest

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
- **Phase 0** — Docker scaffold (FalkorDB + MCP server)
- **Phase 1** — Bulk code ingestion + code RAG + MCP read tools ← _usable daily from here_
- **Phase 2** — Episodic layer + haiku writer hook
- **Phase 3** — Installer CLI (install/uninstall/doctor, Claude Code scope)
- **Phase 4** — ~~Codex adapter~~ dropped (episodic writes require haiku through the Claude Code account; Codex cannot drive that)
- **Phase 5** — Code↔memory graph coupling (data-driven, only if anchor quality warrants it)

## Key decisions already made (do not re-open)
- Memory is a **proprietary layer**, not Graphiti (Graphiti's per-episode LLM calls make bulk ingestion too costly)
- Bulk ingestion = **zero LLM** (pure embedding, computed in-process by the MCP server)
- Master agent is **read-only**; all memory writes go through the distiller (extractor haiku → arbiter sonnet)
- Episodic memory is written at **SessionStart from past transcripts** (ledger-gated), not at Stop — the transcript on disk is the durable source
- Distiller prompts live in `plugins/memory/hooks/prompts/*.md` (extractor.md / arbiter.md), never inline in Python
- Orchestrator (worker / worker-small / roadmapper) is the entry point for **backlog-driven work only**, not for interactive sessions
- `SubagentStop` does **not** write episodic memory; it only reconciles code RAG
- Embedding runs **inside the `mcp` container** (SentenceTransformers, cached model volume) — no standalone embedding service (Ollama/TEI) to deploy or babysit
- Code chunking = **per function** (AST, tree-sitter); docstrings kept (signal for embedding quality)

## Open decisions (to resolve during implementation)
- `group_id` hashing: `git remote URL` preferred, `repo_path` fallback (needs confirmation)
- Whether to cache raw code content alongside the reference (currently: reference only, cache optional)
- Concurrency lock strategy for multi-session bulk ingest on the same repo

<!-- market-mem:start -->
## Memory graph (managed by market-mem — do not edit this block)
This project's graph id: `group_id = "eba78fe1da30f0e9"` — pass it to every memory MCP tool.
- Conceptual code question ("where is X handled?") → `code_search(group_id="eba78fe1da30f0e9", query=…)` BEFORE Grep/Read.
- Architecture decision, refactor, or reopening a past choice → `memory_search(group_id="eba78fe1da30f0e9", query=…)` before acting.
- Empty results are cheap and expected — call speculatively.
<!-- market-mem:end -->
