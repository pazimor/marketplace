# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A **Claude Code plugin marketplace** ("ECC"-style) that distributes:
- **Skills and agents** for Claude Code (and eventually Codex)
- A **proprietary memory system** — a local RAG layer combining code indexing (bulk, zero-LLM) with episodic memory (written by haiku at session end)

The repo is currently in the design/planning phase. `ROADMAP.md` and `DB_SCHEMA.md` are the authoritative specs; no code has been written yet.

## Architecture overview

### Plugin layout (target structure)
```
marketplace/
├── .claude-plugin/marketplace.json   # plugin catalogue
├── plugins/
│   ├── memory/                       # memory system plugin
│   │   ├── .claude-plugin/plugin.json
│   │   ├── hooks/hooks.json
│   │   ├── agents/                   # haiku sub-agent (episodic writer)
│   │   ├── skills/
│   │   └── .mcp.json
│   ├── skills-pack/
│   └── agents-pack/
├── installer/                        # CLI: install/uninstall/status/doctor
└── docker/                           # shared FalkorDB + Ollama + MCP server
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
| Code index | `:CodeChunk` | Bulk at `SessionStart`, AST → Ollama embed | Zero LLM |
| Episodic memory | `:MemoryEpisode` | `haiku` at hook `Stop` (delta only) | haiku only |

**Key invariants:**
- Code is stored **by reference** (`path + [start_line, end_line]`), never copied into the DB
- `content_hash` gates re-embedding — only changed symbols are re-embedded
- Vector index uses `MAX_DIM = 2048` with zero-padding; switching embedding models = recompute, never index recreation
- Embedding models: `microsoft/graphcodebert-base` (code, 768d) and `nomic-ai/nomic-embed-text-v1.5` (memory, 768d)
- `group_id` = `hash(git remote URL)` (fallback: `hash(repo_path)`); one FalkorDB graph per project

### MCP tools
**Read (exposed to master):** `memory_search`, `memory_query`, `code_search`, `code_fetch`

**Safe writes (exposed to master):** `memory_immunize`, `memory_release`, `memory_extend`

**Hidden writes (haiku/debug only):** `memory_add`, `memory_delete`, `code_add`, `code_edit`, `code_delete`

### Hook design
| Hook | Action |
|---|---|
| `SessionStart` | `docker compose up` → embedding coherence check → bulk ingest (background, non-blocking) |
| `PostToolUse (Write/Edit)` | Re-embed changed symbols (hash-gated) + mark session "dirty" |
| `Stop` (master) | Two-stage gate: if dirty → summon haiku on delta → `memory_add`; else exit immediately |
| `SubagentStop` | Code-RAG reconcile only (git diff → upsert changed symbols); no haiku, no memory write |
| `SessionEnd` | Flush if still dirty + `docker compose stop` (keep volume) |

### Retention policy
- Episodic facts: invalidated after 30 days, hard-deleted after 30 days grace (60-day total window)
- `immune = true` exempts a fact from all purges; controlled via `memory_immunize`/`memory_release`/`memory_extend`

## Roadmap phases
- **Phase 0** — Docker scaffold (FalkorDB + Ollama + MCP server)
- **Phase 1** — Bulk code ingestion + code RAG + MCP read tools ← _usable daily from here_
- **Phase 2** — Episodic layer + haiku writer hook
- **Phase 3** — Installer CLI (install/uninstall/doctor, Claude Code scope)
- **Phase 4** — Codex adapter (MCP-only; hooks not supported by Codex)
- **Phase 5** — Code↔memory graph coupling (data-driven, only if anchor quality warrants it)

## Key decisions already made (do not re-open)
- Memory is a **proprietary layer**, not Graphiti (Graphiti's per-episode LLM calls make bulk ingestion too costly)
- Bulk ingestion = **zero LLM** (pure Ollama embedding)
- Master agent is **read-only**; all writes are delegated to haiku
- Haiku is called only when session is "dirty" (two-stage deterministic gate)
- `SubagentStop` does **not** write episodic memory; it only reconciles code RAG
- Ollama runs **inside Docker** (`mem_net`), not reusing the host's Ollama instance
- Code chunking = **per function** (AST, tree-sitter); docstrings kept (signal for embedding quality)

## Open decisions (to resolve during implementation)
- `group_id` hashing: `git remote URL` preferred, `repo_path` fallback (needs confirmation)
- Whether to cache raw code content alongside the reference (currently: reference only, cache optional)
- Concurrency lock strategy for multi-session bulk ingest on the same repo
