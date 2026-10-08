# CLAUDE.md

Guide for Claude Code when working in this repo.

## What this repo is

A **Claude Code plugin marketplace** that distributes three serverless plugins: `orchestration`
(described below), `level-design` (taste and method for 3D level design, `CANON:9`) and
`agents-info` (a agents-info Mod built on function hooks, `CANON:13`).
`orchestration` only produces markdown files in the user's repo:
- `.claude/roadmap.md`: specs, milestones with DoD, tasks with stable IDs, claims (skill `roadmap-tracker`)
- `.claude/canon/*.md`: expectations, conventions, tests, invariants, each entry with its provenance `[USER:<name>]` / `[MODEL]` (skill `canon-tracker`)
- the `scribe` and `orchestrator` agents and the main agent ("default") are three equal peers that talk to each other directly (`CANON:17`): the scribe keeps canon + roadmap; whoever framed the request with the user hands a framing brief to the `orchestrator` agent, which delegates each scoped task while choosing **the effort**, checks the results on return and reports back; the scribe captures what is implicit into the canon

This repo applies its own plugin to itself: **read `.claude/canon/*.md` before acting.**

## Directory layout

```
.claude-plugin/marketplace.json     # catalog (orchestration, level-design, agents-info)
plugins/orchestration/
├── .claude-plugin/plugin.json      # plugin semver version
├── agents/scribe.md                # scribe: peer, keeps canon + roadmap, does not write code, does not relay anything
├── agents/orchestrator.md          # orchestrator: peer, delegates, checks, reports back to its caller
├── agents/executor-{low,medium,high,xhigh,max}.md   # executors: differ only by `effort`
└── skills/{roadmap-tracker,canon-tracker}/SKILL.md   # owners of the grammars
plugins/level-design/
├── .claude-plugin/plugin.json      # plugin semver version
├── agents/level-design-reviewer.md # judges from screenshots (read-only)
└── skills/{level-design-taste,level-design-build}/  # SKILL.md + references/
plugins/agents-info/                # Mod (function hooks, API in early access, `CANON:56`)
├── .claude-plugin/plugin.json      # version, options (`userConfig`), `types` contract
├── hooks/{hooks.json,register.tsx,recap.ts}   # hooks module + pure model
├── types/index.d.ts                # state declared to the engine (PluginState)
└── tests/                          # `claude plugin test plugins/agents-info`
.claude/types/                      # engine declarations (2.1.287), regenerated locally on each version, untracked
docs/grammar.md                     # canon + roadmap grammar in EBNF (describes the SKILL.md files, does not decide them)
docs/mascots-preview.html           # band mascots (scripts/preview-mascots.mts)
docs/agents-info-preview.{html,svg} # README band, drawn by the Mod's code (scripts/preview-agents-info.mts)
docs/agents-info-pane-preview.{html,svg} # README /agents-info pane, same script
tools/bench.md                      # method of the delegation benchmarks (executors, scribe), to re-run them
tools/skill_audit.py                # usage audit of skills and agents, from the transcripts
scripts/validate.py                 # stdlib validator: manifests, frontmatter, canon, roadmap
scripts/tests/                      # validator tests (unittest)
.github/workflows/ci.yml            # CI: validate + plugin install smoke test
CHANGELOG.md
```

## Commands

```sh
python3 scripts/validate.py .                       # 0 errors expected; --strict also fails on WARN
python3 -m unittest discover -s scripts/tests -q    # validator tests
claude plugin validate . && claude plugin validate plugins/orchestration
claude plugin validate plugins/agents-info && claude plugin test plugins/agents-info
```

Install smoke test, in a clean HOME: `claude plugin marketplace add ./` then
`claude plugin install orchestration@marketplace` then `claude plugin list --json`. No
authentication is required.

## Working rules

- **Bump the version on every change (`CANON:5`).** Modifying a skill or an agent of
  `plugins/orchestration/` = bumping `version` in `plugins/orchestration/.claude-plugin/plugin.json`
  (patch: rewording; minor: new behavior, agent or skill; major: canon/roadmap grammar changed or agent/skill removed) **and** adding an entry to `CHANGELOG.md`.
  A catalog change also bumps `version` in `.claude-plugin/marketplace.json`.
  Run `python3 scripts/validate.py .` before committing.
- **Models (`CANON:22`, `CANON:19`).** Only the `scribe` sets its `model` (the most economical model);
  the orchestrator inherits the session's model and passes the model of each executor at call time,
  starting from the most economical one that an independent executable criterion can verify. A model name appears only on the `model:` line of an agent's frontmatter,
  never in the text of agents, skills, manifests, README or this file (`validate.py` rejects it).
- **Stay generic (`CANON:4`).** No particular project or tool (Unity, prefab…) in the distributed agents and skills:
  those details live in the user project's canon.
- **Grammars belong to the SKILL.md files (`CANON:2`).** If a grammar rule changes,
  edit the SKILL.md, then `docs/grammar.md` and `scripts/validate.py` along with their tests.
- **Canon: never delete anything.** An outdated entry is struck through `~~…~~` and followed by
  `— obsolete YYYY-MM-DD: <reason>`. A `[USER]` entry is deprecated only on the user's decision.
- **Plugin agents**: `hooks`, `mcpServers` and `permissionMode` are ignored in their frontmatter. The effort is set by `effort` in the frontmatter, or by `opts.effort` in a
  workflow (`CANON:6`); the Agent tool accepts `effort` at call time only since 2.1.293 (`CANON:26`).
- Everything is written in English — skills, agents, docs, canon, CHANGELOG, code comments and UI strings — with a directive tone in skills and agents (`CANON:40`).
