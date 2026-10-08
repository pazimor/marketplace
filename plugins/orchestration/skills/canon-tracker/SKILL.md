---
name: canon-tracker
description: Keep the project's canon in versioned markdown files (`.claude/canon/` — expectations, conventions, test instructions, invariants), each entry carrying its provenance, `[USER:<name>]` (untouchable) or `[MODEL]` (can be downgraded). Use whenever the conversation touches on what the user expects of the product, how the project does things, how testing works, what must not break, or a constraint or convention to keep in mind — and systematically before writing code on the project and at the close of every task, even if the word "canon" is never spoken.
---

# Canon tracker — the implicit, written as it goes

What gets worked out on the first pass — how we test, what must not break,
what the user actually expects — is never written down and dies with the
conversation. The canon is where it gets written, entry by entry, with its
source. The file is the canon; the conversation is only a draft.

## Where the canon lives

- **Source of truth**: `.claude/canon/` at the root of the project's repo.
  Committed, versioned, synced through git — it belongs to the project, not
  to a person.
- **No memory mirror.** Unlike the roadmap, the canon is never copied into
  auto memory (`~/.claude/projects/…`): it belongs to the repo and to anyone
  who clones it.
- **Themed files**, one theme per file:
  - `expectations.md` — what the user expects of the product (intended
    behaviors, non-goals, priorities).
  - `conventions.md` — the project's ways of doing things (naming, structure,
    style, mandated tooling).
  - `tests.md` — how we verify: exact commands, where to run them from, what a
    healthy output looks like.
  - `invariants.md` — states and behaviors that must **NEVER** be broken.
- A new, clearly distinct theme can justify an extra file (`perf.md`,
  `security.md`…). Never a `misc.md` or any catch-all: an entry that fits
  nowhere signals a theme that needs a name.

## Entry grammar (never deviate from it)

An entry is **one** point, fitting on one line (one sentence, two at most).
Never floating prose, never a paragraph outside an entry.

```
- `CANON:n` [USER:<name> YYYY-MM-DD] <the point>
- `CANON:n` [MODEL YYYY-MM-DD] <the point>
```

- The `CANON:n` IDs are **stable, increasing, and unique across the whole
  folder** (not per file): the next free number is looked up across all of
  `.claude/canon/`. Never renumbered, never reused, even after deprecation.
- The date is the date the entry was written (or the confirmation date, in
  case of promotion).
- `<name>` is the name or identifier of the person who stated or validated
  the point; when in doubt, ask rather than invent.

Full example (`.claude/canon/tests.md`):

```markdown
# Tests

- `CANON:12` [USER:pazimor 2026-08-14] The suite runs with `pytest -q` from the
  repo root; never from a subfolder (the fixtures break).
- `CANON:13` [MODEL 2026-08-14] `pytest -q tests/test_graph.py` takes ~40 s: the
  first call downloads the model, the following ones are instant.
- `CANON:14` [USER:pazimor 2026-08-20] A test that touches the network is rejected in
  review, even when marked `skip`. (promoted from MODEL)
- ~~`CANON:9` [MODEL 2026-07-02] Tests run via `make test`.~~
  — obsolete 2026-08-14: `make test` was removed, replaced by `CANON:12`.
```

## Provenance — the central rule

**`[USER:<name>]` = stated or explicitly validated by the human. UNTOUCHABLE.**
Never rewritten, never deleted, never contradicted, never "improved". A
conflict — between two `[USER]` entries, or between the observed code and a
`[USER]` entry — is **reported to the user** and stops there; it is never
fixed on its own authority.

**`[MODEL]` = inferred or observed by the agent while working.** When any
`[USER]` entry conflicts with it, the `[MODEL]` entry is downgraded
automatically: the user is right. A `[MODEL]` entry becomes `[USER:<name>]`
only on the user's **explicit confirmation** — never because it looks solid,
never because it is old, never because the code has verified it.

**Nothing is ever deleted.** An entry that has become false is struck through
(`~~text~~`) with its reason and date, and stays in place: the canon's history
is part of the canon.

## Common operations

**Add an entry** — pick the themed file, take the next free `CANON:n` across
the whole folder, and write one line following the grammar above. A point that
comes from the user (stated or validated in the conversation) → `[USER:<name>]`.
A point observed while working → `[MODEL]`. A `[USER]` entry carries only what
the user stated or validated: details taken from another entry or observed
while working go into a separate `[MODEL]` entry that cites it. Never touch
neighboring entries along the way.

**Promote `[MODEL]` → `[USER:<name>]`** — only after the user's explicit
confirmation on that specific point ("yes, that's the rule"). Promotion keeps
the ID, retags the line with the name and the **confirmation date**, and
appends `(promoted from MODEL)` at the end of the line. Without explicit
confirmation: the entry stays `[MODEL]`, full stop.

**Deprecate an entry** — strike through the text (`~~…~~`), add below it or at
the end of the line `— obsolete YYYY-MM-DD: <reason>` and, where relevant, the
ID of the entry that replaces it. A `[USER]` entry is deprecated **only** on
the user's decision.

**Resolve a conflict** — rewrite nothing. Cite the entries involved with their
IDs, describe the contradiction precisely (with what revealed it: code read,
test run, request received), and ask the user which one is authoritative. Until
the answer comes: the `[USER]` entry takes precedence, and the work in progress
aligns with it or stops.

**Initialize the canon** — if `.claude/canon/` does not exist, propose it and
create the four files, each with only its title (`# Expectations`,
`# Conventions`, `# Tests`, `# Invariants`). **Never invent history**: no entry
retroactively inferred from the code at bootstrap time; the canon fills up as
it goes.

## Capture ritual (mandatory at the close of every task)

The scribe agent runs this ritual at the close of **every** task, before
ticking anything off, based on the conversation and the findings reported back
by the orchestrator.

1. Ask explicitly: **"what implicit point was worked out during this pass?"**
2. Go back over the conversation: each request, decision, or validation from
   the user along the way → a `[USER:<name>]` entry (expectations, conventions,
   invariants, depending on the theme).
3. Go back over the work: a test command that actually works, an observed
   invariant, a pitfall encountered, a constraint discovered → a `[MODEL]`
   entry.
4. Write the entries **before** ticking the task off in the roadmap, then
   remind that `.claude/canon/` still needs to be committed.
5. Nothing new? Say so explicitly — that is a valid answer, not a reason to
   skip the step.

## Read gate (before any code action)

Before writing or modifying code in the project, read the relevant canon files
(at minimum `invariants.md` and `conventions.md`; `tests.md` as soon as
verification is involved; `expectations.md` as soon as behavior is involved).
A `[USER]` entry takes precedence over any intuition of the model, any general
habit, and any precedent found elsewhere in the code. A `[MODEL]` entry serves
as a hint, not a law.

## Guardrails

- **Surgical** edits: add a line, strike through a line, retag a line. Never
  rewrite a whole file, never renumber, never "clean up" or reword existing
  entries.
- `[USER]` always takes precedence, over the model as over the code. The model
  flags, it does not decide.
- A vague entry is worthless: a point that cannot be verified (exact command,
  observable behavior, applicable rule) must be reworded or asked about.
- The canon is not a logbook: no session narrative, no "I did X", only durable
  points.
- Never invent canon to fill space: four nearly empty files that are true beat
  a plausible but false canon.
