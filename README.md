<div align="center">
  <img src="assets/marketplace.png" width="100" alt="marketplace logo"/>

  # marketplace

  **A Claude Code plugin marketplace: keep the implicit written down — roadmap, canon, and orchestration, as plain markdown files in your repo.**

  [![Plugins](https://img.shields.io/badge/plugins-roadmap%20%7C%20orchestration-informational)](#installation)
  [![Runtime](https://img.shields.io/badge/runtime-none-brightgreen)](#why)
  [![Sync](https://img.shields.io/badge/sync-git-F05032?logo=git&logoColor=white)](#why)

</div>

---

Everything worked out in a first pass — what you actually expect, how this module is really tested, which behaviour must never break — is agreed in the conversation and written nowhere. Change the conversation, change the agent, change the machine: it's gone, and you explain it again. **marketplace** ships the skills that make that implicit knowledge a file.

## Why

No server, no Docker, no database, no CLI. Every artefact is markdown in your repo (`.claude/roadmap.md`, `.claude/canon/`), read by the agent before it acts and written by the agent when it closes a task. Machine-to-machine sync is `git pull`; team review is a diff.

The file is the format. A server would only ever be a transport — never the other way around.

## The three pillars

Two plugins, three skills.

### `roadmap-tracker` — the plan as a file

A strict-grammar markdown roadmap: **specs are canon** (the design is already settled, implementation doesn't re-decide), milestones carry an observable Definition of Done, tasks have stable IDs (`ROADMAP:TASK:7`) that are never renumbered or reused, plus claims (`[~] claimed by <user>`) and declared dependencies. Source of truth lives in Claude Code's native auto-memory, mirrored after every edit to `.claude/roadmap.md` so it travels with the repo.

It also carries a Definition of Done per task type — feature, bug, test, doc, infra — each criterion **demonstrated** (command run, output quoted), never asserted.

### `canon-tracker` — the implicit, with provenance

The project canon lives in `.claude/canon/`, one file per theme: `attentes.md` (what you expect from the product), `conventions.md` (how things are done here), `tests.md` (the exact commands and what a healthy output looks like), `invariants.md` (what must never break).

Every entry is one line and carries its source:

```markdown
- `CANON:12` [USER:eddy 2026-08-14] The suite runs with `pytest -q` from the repo
  root; never from a subdirectory (fixtures break).
- `CANON:13` [MODEL 2026-08-14] First run of `tests/test_graph.py` takes ~40 s —
  it downloads the model; later runs are instant.
```

- **`[USER:<name>]`** — said or validated by a human. **Untouchable**: never rewritten, never "improved", never contradicted. A conflict is reported to you and stops there.
- **`[MODEL]`** — inferred by the agent while working. Demoted on sight against any `[USER]` entry, and promoted to `[USER]` only on an explicit confirmation — never because it turned out true a few times.

Nothing is deleted: an entry that goes stale is struck through with its date and reason and stays in place. And it gets filled by a **capture ritual** run at every task closure — "what implicit thing did we work out during this pass?" — so the writing-down isn't left to good intentions.

### `orchestrateur` — Fable orchestrates, Opus codes

A workflow, made explicit: the model carrying the session **never writes code**. It reframes the request, asks the open questions up front, scopes the work into tasks that each carry an objective, a file perimeter, an executable success criterion and an explicit out-of-scope list — then delegates each one to an Opus agent.

The rest is verification: a delegated agent's report is a claim, not proof, so the orchestrator runs the success criterion itself and reads the output. Before any delegation it passes a mandatory read gate over the canon and the roadmap; at closure it runs the capture ritual and only then ticks the box.

## Installation

Requires Claude Code. Nothing else.

```
/plugin marketplace add pazimor/marketplace
/plugin install roadmap
/plugin install orchestration
```

Then, in your project, ask the agent to initialise the roadmap and the canon — it will create `.claude/roadmap.md` and `.claude/canon/*.md` with empty, honest files (it never back-fills invented history). Commit them: that's the sync mechanism.

The skills trigger on their own — talk about a milestone, a task, a convention, a test command, or ask for a feature, and the right one loads.

## Repo layout

```
marketplace/
├── .claude-plugin/marketplace.json
├── plugins/
│   ├── roadmap/skills/         # roadmap-tracker, canon-tracker
│   └── orchestration/skills/   # orchestrateur
└── .claude/roadmap.md          # this project's own roadmap, dogfooded
```

## Legacy — being removed

This repo used to distribute a heavier `memory` plugin: a Docker stack (FalkorDB + an MCP server), a semantic code index, embeddings, and a transcript distiller. That approach is **abandoned** — ripgrep plus current models make the code index unnecessary, and Claude Code's native memory covers the memory need.

The old pieces are still on disk and still referenced by `.claude-plugin/marketplace.json`:

- `plugins/memory/` — hooks, distiller prompts, `.mcp.json`
- `market-mem/` — Docker stack, FalkorDB, ingestion, graph builder
- `installer/` — the `market` CLI

They are **deprecated, not gone**. Nothing is dismantled before the new workflow is validated in real use (`ROADMAP:TASK:8`); removal is milestone M3. If you have the old stack installed it keeps working for now, but don't build on it. See [`.claude/roadmap.md`](.claude/roadmap.md) for the full plan.

## Roadmap

| Milestone | Scope | Status |
|---|---|---|
| **M1** | File foundations — roadmap plugin, canon skill with provenance, installable with no server at all | 🚧 active |
| **M2** | Fable → Opus orchestration — capture ritual and read gate, validated in real use | planned |
| **M3** | Legacy teardown — Docker, FalkorDB, embeddings and distiller removed for good | planned |
| **M4** | Team tier — a minimal MCP file server for teams without git: standard bearer-token auth per the MCP spec, versioned markdown store, optimistic concurrency (a push on a stale version is rejected, then re-fetch/merge/re-push). **Like GitHub, not on GitHub** | planned |

The solo tier stays strictly server-free, M4 included.
