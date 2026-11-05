---
name: roadmap-tracker
description: >-
  Keep the project roadmap in `.claude/roadmap.md`, a single versioned copy that holds only
  what is open (specs, unfinished milestones with DoD, open tasks with stable IDs, claims),
  and move closed work to an append-only monthly archive in `.claude/journal/`. Use whenever
  the user talks about roadmap, backlog, milestone, spec, task or progress — adding or editing
  an entry, claiming or continuing a task, marking something done, asking where things stand,
  migrating an old roadmap — even when the word "roadmap" is not said explicitly.
---

# Roadmap tracker — what is open, in one file

The roadmap lives in a markdown file with a strict grammar. The spec is
authoritative, the file is the state of what is still open, the archive keeps
what was closed, and progress is reported by editing these files — surgically,
without ever breaking their grammar.

## Where the roadmap lives

- **Single copy**: `.claude/roadmap.md` at the root of the project's repo,
  committed with the project — that is what carries it from one machine to
  another. No copy is kept in auto-memory.
- **Old copy in auto-memory** (`~/.claude/projects/<project>/memory/roadmap.md`,
  left by an earlier version of this skill): the more recent of the two wins,
  once (compare modification dates, report any conflict). Then move the memory
  copy out of the memory folder (for example to a sibling
  `memory-archive-YYYY-MM-DD/` folder) — never delete it without the user's
  decision — and report it.
- **Layout switch** (shared with `canon-tracker`): the project is on **layout
  v2** when `.claude/journal/` is a directory; otherwise it is on **layout v1**
  (§ "Layout v1").
- **Archive** (layout v2) — `.claude/journal/roadmap-YYYY-MM.md`, one file per
  month, append-only: closed tasks, finished milestones, retired specs, and the
  history lines of tasks (written while the task was open), copied verbatim. Only the files named
  `roadmap-YYYY-MM.md` (this skill) and `canon-YYYY-MM.md` (skill
  `canon-tracker`) directly in `.claude/journal/` belong to this plugin. Leave
  every other file of that folder alone.

## Grammar (never deviate from it)

Three families of stable IDs, numbered in ascending order, **never renumbered
or reused**, even after archiving or deletion:
`ROADMAP:SPEC:n`, `ROADMAP:MILESTONE:n`, `ROADMAP:TASK:n`. The next free number
of a family looks at the roadmap and at the archive.

### Roadmap file

Example, `.claude/roadmap.md`:

```markdown
# Roadmap

## Specs

- `ROADMAP:SPEC:1` **CSV export** [active]
  - Canon: `docs/export.md`, the settled design.

Rules:
- One file per report, UTF-8, comma-separated.

## M2 — Export (`ROADMAP:MILESTONE:2`, active)

Users take their reports out of the app (scope decision 2026-11-02: CSV only).

Milestone DoD: `pytest -q tests/test_export.py` green, and an exported report opens in a spreadsheet.

- [~] `ROADMAP:TASK:4` Export a report as CSV — remains: the date column, checked by `pytest -q tests/test_export.py`. _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:3; claimed by alex; history: roadmap-2026-11.md)_
- [ ] `ROADMAP:TASK:5` [BUG] A comma inside a field shifts the columns _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:4)_

## Backlog (no milestone)

- [ ] `ROADMAP:TASK:6` [RESEARCH] Compare the export libraries
```

Conventions:

- The roadmap holds **only what is open**: specs `[draft]` or `[active]`;
  milestones `planned` or `active`, each with its header, one to three lines of
  description and its DoD; tasks `[ ]` and `[~]`.
- Checkboxes: `[ ]` todo · `[~]` in_progress (always accompanied by
  `claimed by <user>`). A blocked task stays `[~]` with `blocked: <reason>` in
  its suffix. **No `[x]` in the roadmap**: a closed task lives in the archive.
- The italic suffix groups, in this order and separated by `; `:
  `implements <SPEC...>`, `depends on <TASK...>`, `claimed by <user>`,
  `blocked: <reason>`, `history: <file>` — the last one names a
  `roadmap-YYYY-MM.md` of `.claude/journal/` that holds earlier versions of the
  line.
- **One line per open task**: aim at ~300 bytes; over 600 is an exception
  that the line itself justifies. What was done goes to the archive; the line
  keeps what remains.
- References (`depends on`, `implements`) resolve against the roadmap and the
  archive: a dependency closed in the archive counts as done.
- Normalized title prefixes: `[BUG]`, `[PLACEHOLDER]` (undetailed placeholder),
  `[RECURRING]`, `[BACKGROUND]` (background task), `[RESEARCH]`. The implicit
  type of a task without a prefix is `feature`.
- Scope decisions are dated in the text ("sponsor decision 2026-07-30"); the
  archive carries the history.

### Archive file

Example, `.claude/journal/roadmap-2026-11.md`:

```markdown
# Roadmap archive — 2026-11

## Closed tasks

- [x] `ROADMAP:TASK:1` Project skeleton — closed 2026-11-01: `make check` green on a fresh clone.
- [x] `ROADMAP:TASK:2` Run the tests on every push — closed 2026-11-02: CI run 18 green. _(depends on ROADMAP:TASK:1)_
- [x] `ROADMAP:TASK:3` Read a report's rows — closed 2026-11-03: `pytest -q tests/test_rows.py` green, 12 passed. _(implements ROADMAP:SPEC:1)_

## M1 — Setup (`ROADMAP:MILESTONE:1`, done)

The project builds and its tests run on every machine.

Milestone DoD: `make check` green on a fresh clone; met 2026-11-02.

## History

- [~] `ROADMAP:TASK:4` Export a report as CSV — header and rows done 2026-11-03 (`pytest -q tests/test_export.py`: 4 of 5 green); remains: the date column. _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:3; claimed by alex)_
```

- Title `# <any text>`. Section titles are free, in any language, and never
  relied on.
- **Append-only**: lines are copied verbatim, at the end of the current
  month's file; a written line is never edited, moved or deleted.
- Lines are classified by their checkbox only, on top-level task lines:
  `- [x]` = the task is closed (once, across all the archive files);
  `- [ ]` or `- [~]` = a history line of a task: written while the task is
  open, it stays when the task is closed later (append-only), and it may
  repeat.
- **Each task ID is open in the roadmap or closed in the archive, never both.**
  A history line is valid for a task that is either one of the two.
- Finished milestone blocks (header, description, DoD) and retired specs are
  copied there verbatim.

## Common operations

**"Where do we stand?"** — read the roadmap and answer with: milestones and
their done ratio (closed tasks counted in the archive), `[~]` tasks claimed,
next unblocked tasks (all dependencies closed). Do not paraphrase the whole
file.

**Add a spec / a milestone / a task** — take the next free number in the
family (roadmap and archive), follow the grammar, attach the task to its
milestone and spec (`implements`), declare its `depends on`. An unattached
idea goes to the Backlog. Never rewrite existing entries along the way.
**Small work** (one scope, no open question, one verifiable criterion, one
commit) gets no task and no spec: it goes straight to one executor.

**Claim a task** — choose the requested task, otherwise a `todo` whose
dependencies are all closed. If a dependency is open, report it and stop.
Mark `[~]` + `claimed by <user>`, then follow "Implementing a task".

**Close a task** — run through the Definition of Done for its type (below),
with evidence. Everything passes → move its line to the end of the current
month's archive, ticked `[x]`, its `claimed by` removed and the evidence
written before the suffix (`— closed YYYY-MM-DD: <evidence>`); remove it from
the roadmap; its history lines already in the archive stay where they are
(append-only). A milestone with no open task left → its block (header,
description, DoD) moves to the archive too. Otherwise the task stays `[~]`;
state precisely what is missing. **Never `[x]` without evidence.**

**Condense an open task** — its full previous line goes to the current month's
archive as a history line; the roadmap line keeps its title, `— remains: …`,
and `history: <file>` at the end of its suffix.

**Retire a spec** — its block moves to the archive verbatim.

**Migrate a v1 roadmap** — a work item the user launches:

1. Create `.claude/journal/` if needed.
2. Closed tasks (`[x]`) and finished milestone blocks go to the archive,
   verbatim, in the month of their closing date written in the line, otherwise
   of the last date the line cites. Retired specs go there too.
3. Nothing is ticked `[x]` without evidence: a task with no evidence of being
   done stays open.
4. Long open lines are condensed: their full line goes to the current month's
   archive as a history line, and the roadmap line gets `history: <file>`.
5. Check that each task ID is open in the roadmap or closed in the archive,
   never both, then run the marketplace's validator on the project root when
   it is available.

**Always finish with**: remind the user that `.claude/roadmap.md` and
`.claude/journal/` still need to be committed.

## Implementing a task

1. **Spec first**: read the task's spec(s) and the repo docs they cite. The
   spec has already settled the design — the implementation does not re-decide
   it. An ambiguous blocking point: ask the user, or mark `blocked` — never
   invent.
2. **Project canon**: pass the read gate of the `canon-tracker` skill
   (`.claude/canon/`) before choosing an approach — a `[USER]` rule can
   invalidate a plan.
3. **Plan (gate)**: split the work into verifiable increments — each increment
   has an objective success criterion (test, command, demonstrated behavior).
   Default order: contracts/schemas → logic → interfaces → UI → docs. **The
   framing the user validated — or, for small work, the user's request — is
   the go-ahead**: do not wait for another one. Without either, present the
   plan and wait for the go-ahead before writing any code.
4. **Increments**: an increment whose verification does not pass is not done.
   Make surgical changes. Do not commit — the working tree goes back to the
   user.
5. **Wrap-up**: DoD, then close the task (see above). If a gap is found
   between the spec and the actual code, inside a validated framing: amend the
   spec and record the amendment as the agent's decision (decision entry,
   grammar: `canon-tracker`). Ask the user first only when the amendment
   touches what is reserved to them.

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

## Layout v1 (projects not migrated yet)

No `.claude/journal/` folder: nothing moves to an archive. A closed task stays
in the roadmap, ticked `[x]` with its `claimed by` removed; a milestone whose
tasks are all `[x]` stays in place with `done` in its header; a spec is marked
`[retired]`. The suffix has no `history:` element. Propose the migration; the
user launches it.

## Guardrails

- The roadmap and its archive are the only source of truth: no progress state
  held mentally or in the conversation alone.
- Minimal edits: change a checkbox or a suffix, add an entry, move a closed
  line to the archive — never a global rewrite, never a renumbering.
- The archive is append-only: never edit, reorder or delete a line written
  there.
- A check that cannot be run (external service, missing secret) is not ticked
  on trust alone: it is escalated to the user.
- If the file cannot be found, offer to initialize an empty one that follows
  the grammar above — never invent a history.
