<div align="center">
  <img src="assets/marketplace.png" width="100" alt="marketplace logo"/>

  # marketplace

  **A Claude Code plugin marketplace: keep the implicit written down — roadmap, canon, and orchestration, as plain markdown files in your repo.**

  [![Plugin](https://img.shields.io/badge/plugin-roadmap-informational)](#installation)
  [![Runtime](https://img.shields.io/badge/runtime-none-brightgreen)](#why)
  [![Sync](https://img.shields.io/badge/sync-git-F05032?logo=git&logoColor=white)](#why)

</div>

---

Everything worked out in a first pass — what you actually expect, how this module is really tested, which behaviour must never break — is agreed in the conversation and written nowhere. Change the conversation, change the agent, change the machine: it's gone, and you explain it again. **marketplace** ships the skills that make that implicit knowledge a file.

## Why

No server, no Docker, no database, no CLI. Every artefact is markdown in your repo (`.claude/roadmap.md`, `.claude/canon/`), read by the agent before it acts and written by the agent when it closes a task. Machine-to-machine sync is `git pull`; team review is a diff.

The file is the format. A server would only ever be a transport — never the other way around.

## The three pillars

One plugin (`roadmap`), two skills and one agent.

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

### `scribe` + `orchestrateur` (agents) — equal peers beside your main agent, executors code

A workflow, made explicit, split in three roles so the expensive model only works where it pays off. The main agent (the default one you talk to), the scribe and the orchestrator are **equals**: none is the entry point, and each can message the others directly (short messages that point to IDs and paths, never copies). **No role above the executors ever writes code.**

- **`scribe` — the pen.** It keeps the canon and the roadmap: whoever talks with you sends it the decisions to write down, the orchestrator sends it its findings, and at closure it runs the capture ritual — what implicit thing was settled, and what got stuck in the orchestration itself — and only then ticks the box. It is not a relay, so its context doesn't fill up with copies.
- **`orchestrateur` — delegation and verification.** It splits the scoping file into tasks that each carry an objective, a file perimeter, an executable success criterion and an explicit out-of-scope list, delegates each one choosing the **reasoning effort** by the nature of the work, writes the multi-agent workflow when you explicitly asked for one, and runs every success criterion itself — a delegated agent's report is a claim, not proof. It reports back to whoever called it and sends its findings to the scribe; it never talks to you directly.
- **`executant-low` … `executant-max` — the executors.** Effort can't be passed on a plain subagent call, so the five executors differ only by `effort`: picking the executor picks the effort.

Each agent pins its model in its own frontmatter — the only place a model is ever named. The scribe runs on an economical model, the orchestrator on the most capable allowed one, the executors on a smaller one; the most expensive family is refused by the validator. The orchestrator never passes a model on a call.

Setup, once per machine:

- nothing to configure: start the session with your usual main agent — the scribe and the orchestrator are summoned as peers when needed;
- optionally, run `/advisor` and pick the orchestrator's model: executors on a smaller model then consult it on their own mid-task.

Before any delegation both agents pass a mandatory read gate over the canon and the roadmap — project specifics (tools, commands, files never to touch) come from there, the agents themselves stay generic.

### `level-design` (plugin) — 3D level-design taste, written down

A second, independent plugin, shaped like [taste-skill](https://github.com/Leonxlnx/taste-skill) but for 3D levels instead of web pages, distilled from a real co-op game project:

- **`level-design-taste`** (skill) — read the brief in one line, set four dials (openness, density, relief, nature), ban the model's defaults (square outlines, tiled flat floors, sprinkled props, lamp carpets, rainbow palettes, enemy models used as props, "done" because the script ran) and pass a measurable pre-flight before showing anything. References for outdoor arenas, interiors, lighting/fog/colour/density, and automatic audits.
- **`level-design-build`** (skill) — the procedure: measure the reference scene instead of eyeballing it, write a spec with three layout concepts and questions for the human, build through an idempotent scripted pass that preserves the human's manual edits, audit, capture from named cameras, review, deliver honestly.
- **`level-design-reviewer`** (agent) — judges screenshots against the project's canon and the spec, ranked blocking / major / minor.

Engine-agnostic: engine and asset-pack specifics belong in your project's canon.

### `session-recap` (mod) — see which agents run, on what, for how much

A third plugin, built on Claude Code's function hooks (mods). It answers "which agent started this session, which subagents did each prompt create, resume or fork, on which model and effort, and what did they cost?":

- **`/session-recap`** opens a pane: the starting agent with its model and effort, the 5-hour / 7-day limits with a linear forecast, a per-prompt timeline (new, resumed, forked, still running), the agent tree, and tokens (input, output, cache read, cache write) by agent × model × effort.
- A one-line band above the prompt keeps the essentials in view.
- Toasts warn at limit thresholds (80 % / 95 % by default), on per-agent and per-session token budgets, when a subagent answers on another model than the one it was spawned on, and when the main agent takes more than a set share of the session.

Read-only: every hook passes the event on unchanged. Thresholds are plugin options (`claude plugin configure session-recap`). Tested on Claude Code 2.1.287; the mods API is early access and may change between releases. Note that a `CLAUDE_CODE_EFFORT_LEVEL` environment variable overrides both the session effort and every agent's `effort` — the recap shows the effort that actually applies.

## Installation

Requires Claude Code. Nothing else.

```
/plugin marketplace add pazimor/marketplace
/plugin install roadmap@marketplace
/plugin install level-design@marketplace   # optional, for 3D level design
/plugin install session-recap@marketplace  # optional, session recap mod (Claude Code ≥ 2.1.287)
```

Then, in your project, ask the agent to initialise the roadmap and the canon — it will create `.claude/roadmap.md` and `.claude/canon/*.md` with empty, honest files (it never back-fills invented history). Commit them: that's the sync mechanism.

The skills trigger on their own — talk about a milestone, a task, a convention, a test command, or ask for a feature, and the right one loads.

## Repo layout

```
marketplace/
├── .claude-plugin/marketplace.json
├── plugins/
│   ├── roadmap/
│   │   ├── skills/             # roadmap-tracker, canon-tracker
│   │   └── agents/             # scribe, orchestrateur, executant-{low,medium,high,xhigh,max}
│   ├── level-design/
│   │   ├── skills/             # level-design-taste, level-design-build (+ references/)
│   │   └── agents/             # level-design-reviewer
│   └── session-recap/
│       ├── hooks/              # register.tsx (hooks module), recap.ts (pure model)
│       ├── types/              # state contract declared to the engine
│       └── tests/              # claude plugin test plugins/session-recap
├── docs/grammar.md             # formal grammar of the canon and roadmap files
├── scripts/validate.py         # stdlib validator — run it on any project using the plugin
├── market-mem/                 # auth skeleton kept for the M4 team server, no features
├── CHANGELOG.md
└── .claude/                    # this project's own roadmap and canon, dogfooded
```

Check a project's roadmap and canon files: `python3 scripts/validate.py <project-root>`.

