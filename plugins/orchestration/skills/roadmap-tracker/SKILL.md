---
name: roadmap-tracker
description: Keep the project roadmap in a markdown file in native memory (specs, milestones with DoD, tasks with stable IDs, claims). Use whenever the user talks about roadmap, backlog, milestone, spec, task or progress — adding or editing an entry, claiming or continuing a task, marking something done, asking where things stand — even when the word "roadmap" is not said explicitly.
---

# Roadmap tracker — the roadmap as a memory file

The roadmap lives in a markdown file with a strict grammar. The spec is
authoritative, the file is the state, and progress is reported by editing
this file — surgically, without ever breaking its grammar.

## Where the roadmap lives

- **Source of truth**: `roadmap.md` in the project's auto-memory folder —
  `~/.claude/projects/<project>/memory/roadmap.md`. Locate the folder with
  `ls -d ~/.claude/projects/*` (the name derives from the repo path); when in
  doubt, the `/memory` command lists the loaded files.
- **Versioned mirror**: after EVERY change, copy the file verbatim into the
  repo under `.claude/roadmap.md` (create it if needed). This mirror, committed
  with the project, is what carries changes from one machine to another.
- **Bootstrapping on a new machine**: if the auto-memory has no `roadmap.md`
  but the repo contains `.claude/roadmap.md`, copy the repo file to the
  auto-memory before any operation — the more recent of the two wins (compare
  modification dates, report any conflict).

## File grammar (never deviate from it)

Three families of stable IDs, numbered in ascending order, **never renumbered
or reused**, even after deletion:
`ROADMAP:SPEC:n`, `ROADMAP:MILESTONE:n`, `ROADMAP:TASK:n`.

File structure:

```markdown
# Roadmap

## Specs

- `ROADMAP:SPEC:1` **Spec title** [draft|active|retired]
  - Canon: <the settled design, references to the repo's docs>

Rules:
- <rule 1>
- <rule 2>

## M1 — Milestone title (`ROADMAP:MILESTONE:1`, planned|active|done)

<Description: why this milestone, dated scope decisions.>

Milestone DoD: <observable, end-to-end replayable criterion.>

- [x] `ROADMAP:TASK:1` Title _(implements ROADMAP:SPEC:1)_
- [ ] `ROADMAP:TASK:2` Title _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:1)_
- [~] `ROADMAP:TASK:3` Title _(claimed by <user>)_

## Backlog (no milestone)

- [ ] `ROADMAP:TASK:4` Title
```

Conventions:

- Checkboxes: `[ ]` todo · `[~]` in_progress (always accompanied by
  `_(claimed by <user>)_`) · `[x]` done. A blocked task stays `[~]` with
  `_(blocked: <reason>)_` in its suffix.
- The italic suffix groups, in this order and separated by `; `:
  `implements <SPEC...>`, `depends on <TASK...>`, `claimed by <user>`,
  `blocked: <reason>`.
- Normalized title prefixes: `[BUG]`, `[PLACEHOLDER]` (undetailed placeholder),
  `[RECURRING]`, `[BACKGROUND]` (background task), `[RESEARCH]`. The implicit
  type of a task without a prefix is `feature`.
- Scope decisions are dated in the text ("sponsor decision 2026-07-30") — the
  roadmap carries its own history.
- A milestone becomes `done` once all its tasks are `[x]`; note it in its
  header without deleting anything.

## Common operations

**"Where do we stand?"** — read the file and answer with: milestones and their
done ratio, `[~]` tasks claimed, next unblocked tasks (all dependencies `[x]`).
Do not paraphrase the whole file.

**Add a spec / a milestone / a task** — take the next free number in the
family, follow the grammar, attach the task to its milestone and spec
(`implements`), declare its `depends_on`. An unattached idea goes to the
Backlog. Never rewrite existing entries along the way.

**Claim a task** — choose the requested task, otherwise a `todo` whose
dependencies are all `[x]`. If a dependency is not done, report it and stop.
Mark `[~]` + `claimed by <user>`, then follow "Implementing a task".

**Complete a task** — run through the Definition of Done for its type (below),
with evidence. Everything passes → `[x]` (remove the `claimed by`). Otherwise →
the task stays `[~]`; state precisely what is missing.

**Always finish with**: copy the file to the repo's mirror `.claude/roadmap.md`,
and remind the user it still needs to be committed.

## Implementing a task

1. **Spec first**: read the task's spec(s) and the repo docs they cite. The
   spec has already settled the design — the implementation does not re-decide
   it. An ambiguous blocking point: ask the user, or mark `blocked` — never
   invent.
2. **Project canon**: pass the read gate of the `canon-tracker` skill
   (`.claude/canon/`) before choosing an approach — a `[USER]` entry can
   invalidate a plan.
3. **Plan (gate)**: split the work into verifiable increments — each increment
   has an objective success criterion (test, command, demonstrated behavior).
   Default order: contracts/schemas → logic → interfaces → UI → docs. **Present
   the plan and wait for the go-ahead before writing any code.**
4. **Increments**: an increment whose verification does not pass is not done.
   Make surgical changes. Do not commit — the working tree goes back to the
   user.
5. **Wrap-up**: DoD + file update + mirror (see above). If a gap is found
   between the spec and the actual code, report it as a proposed amendment to
   the spec; do not correct the spec unilaterally.

## Definition of Done by type

Each criterion must be **demonstrated** (command run, output quoted), not
asserted.

**feature** — spec criteria replayable one by one; targeted tests green;
typecheck/lint green on the touched scope; no dependency left undone.

**bug** — reproduction captured BEFORE the fix; regression test added and
green; test suite of the touched module green.

**test** — the new tests fail when the tested behavior is removed (quick
mutation, or a precise justification); full module test suite green.

**doc** — excerpts and commands run as written; cited paths and names checked,
not assumed.

**infra / chore** — build/migration command run successfully (output quoted);
otherwise the limitation is reported and the task left `[~]`; rollback or
idempotence verified when relevant.

## Guardrails

- The file is the only source of truth: no progress state held mentally or in
  the conversation alone.
- Minimal edits: change a checkbox or a suffix, or add an entry — never a
  global rewrite, never a renumbering.
- A check that cannot be run (external service, missing secret) is not ticked
  on trust alone: it is escalated to the user.
- If the file cannot be found on either side, offer to initialize an empty one
  that follows the grammar above — never invent a history.
