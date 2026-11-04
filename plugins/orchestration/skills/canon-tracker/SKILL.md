---
name: canon-tracker
description: >-
  Keep the project's canon in versioned markdown — pages of the rules in force
  (`.claude/canon/` — expectations, conventions, test instructions, invariants) and an
  append-only monthly journal (`.claude/journal/`) — each rule carrying its provenance,
  `[USER:<name>]` (its substance changes only through a new `[USER]` entry) or `[MODEL]` (can be
  downgraded). Use whenever the conversation touches on what the user expects of the product,
  how the project does things, how testing works, what must not break, or a constraint or
  convention to keep in mind; whenever an agent settles a choice inside a framing the user
  validated, a rule stops being true, or a canon has to be initialized or migrated — and
  systematically before writing code on the project and at the close of every task, even if
  the word "canon" is never spoken.
---

# Canon tracker — the implicit, written as it goes

What gets worked out on the first pass — how we test, what must not break,
what the user actually expects — is never written down and dies with the
conversation. The canon is where it gets written, with its source: a journal
that keeps every entry, and pages that keep only the rules in force. The files
are the canon; the conversation is only a draft.

## Where the canon lives

- **Source of truth**: `.claude/canon/` and `.claude/journal/` at the root of
  the project's repo. Committed, versioned, synced through git — it belongs to
  the project, not to a person.
- **Never in auto memory** (`~/.claude/projects/…`): the canon belongs to the
  repo and to anyone who clones it.
- **Layout switch**: a project is on **layout v2** when `.claude/journal/` is a
  directory; otherwise it is on **layout v1** (§ "Layout v1"), until it is
  migrated (§ "Common operations").
- **Pages** — `.claude/canon/<theme>.md`, one theme per file, holding only the
  rules in force, rewritten clean:
  - `expectations.md` — what the user expects of the product (intended
    behaviors, non-goals, priorities).
  - `conventions.md` — the project's ways of doing things (naming, structure,
    style, mandated tooling).
  - `tests.md` — how we verify: exact commands, where to run them from, what a
    healthy output looks like.
  - `invariants.md` — states and behaviors that must **NEVER** be broken.
- A new, clearly distinct theme can justify an extra page (`perf.md`,
  `security.md`…). Never a `misc.md` or any catch-all: a rule that fits
  nowhere signals a theme that needs a name.
- **Size budget**: 40 KB per page by default; the project's canon may set
  another. A page over budget splits its theme into two named pages.
- **Journal** — `.claude/journal/canon-YYYY-MM.md`, one file per month,
  append-only: every entry ever written, dated, never edited afterwards. The
  canon's history is the journal.
- Only the files named `canon-YYYY-MM.md` (this skill) and `roadmap-YYYY-MM.md`
  (skill `roadmap-tracker`) directly in `.claude/journal/` belong to this
  plugin. Leave every other file of that folder alone.

## Grammar (never deviate from it)

### Journal entries

An entry is **one** point (one sentence, two at most). Never floating prose,
never a paragraph outside an entry. The file opens with a `# <title>` line.

```
- `CANON:n` [USER:<name> YYYY-MM-DD] <the point>
- `CANON:n` [MODEL YYYY-MM-DD] <the point>
```

- A new entry goes at the end of the current month's file (create the file,
  with its title, when the month starts). A long point continues on lines
  indented by two spaces.
- A written entry is never edited, moved or deleted: a correction is a new
  entry.
- The date is the day the entry was written.
- `<name>` is the name or identifier of the person who stated or validated
  the point; when in doubt, ask rather than invent.
- **Decision entry** — a choice the agent settled inside a framing the user
  validated (§ "Who decides"):

  ```
  - `CANON:n` [MODEL YYYY-MM-DD] Decision: <what>; why: <reason>; rejected: <option>; to revert: <how>
  ```

- Content copied verbatim from a v1 canon by a migration is accepted as is:
  struck entries, lines without the leading `- `, indented continuation lines.
- Lines inside fenced code blocks are never entries.

### Page rules

- First non-blank line `# <title>`; group headings `## ` or `### `; blank
  lines; nothing else but rules — no prose.
- A rule is one top-level bullet on **one** line, with no continuation line:

  ```
  - `CANON:n` [USER:<name>] <rule> Sources: `CANON:a`, `CANON:b`.
  - `CANON:n` [MODEL] <rule> Sources: `CANON:a`.
  ```

- Provenance carries **no date**: the dates live in the journal.
- The rule ends with `Sources:` (`Sources :` is tolerated), then every journal
  ID that founds it, each in backticks, separated by `, `, with an optional
  final `.`. No range, no ellipsis. Every ID in `Sources` is an entry of the
  journal.
- No struck line, no "obsolete" marker: a rule no longer in force leaves the
  page, and the journal keeps the entry that retired it.
- A decision in force is a `[MODEL]` rule worded like its decision entry
  (`Decision: …; why: …; rejected: …; to revert: …`).

### IDs

- `CANON:n` is **unique across pages and journal**. A page rule takes a fresh
  ID, never one of its sources. Never renumbered, never reused.
- The next free ID is the maximum over pages and journal + 1, unless the
  project's canon reserves ranges.

### Example

Journal, `.claude/journal/canon-2026-08.md`:

```markdown
# Canon journal — 2026-08

- `CANON:12` [USER:alex 2026-08-14] The suite runs with `pytest -q` from the repo root.
- `CANON:13` [MODEL 2026-08-14] Tests run via `make test`.
- `CANON:14` [MODEL 2026-08-14] `pytest -q tests/test_graph.py` takes ~40 s: the first call
  downloads the model, the following ones are instant.
- `CANON:15` [USER:alex 2026-08-20] Never run the suite from a subfolder: the fixtures break.
- `CANON:16` [MODEL 2026-08-21] Retires the rule founded on `CANON:13`: `make test` was removed.
- `CANON:17` [MODEL 2026-08-27] Decision: network tests live in `tests/net/`, skipped by default; why: the suite must run offline; rejected: a marker on each test; to revert: move them back and drop the skip.
```

Page, `.claude/canon/tests.md`:

```markdown
# Tests

## Running the suite

- `CANON:40` [USER:alex] The suite runs with `pytest -q` from the repo root, never from a subfolder (the fixtures break). Sources: `CANON:12`, `CANON:15`.
- `CANON:41` [MODEL] `pytest -q tests/test_graph.py` takes ~40 s on its first call (it downloads the model), then is instant. Sources: `CANON:14`.

## Network

- `CANON:42` [MODEL] Decision: network tests live in `tests/net/`, skipped by default; why: the suite must run offline; rejected: a marker on each test; to revert: move them back and drop the skip. Sources: `CANON:17`.
```

## Provenance — the central rule

**`[USER:<name>]` = stated or explicitly validated by the human.** Its
substance is never rewritten, contradicted or "improved" by an agent. On a
page, its wording may be tightened and several user entries may fold into one
rule, but its substance changes only through a new `[USER]` journal entry. A
conflict — between two `[USER]` rules, between the observed code and a
`[USER]` rule, or between a plan and one — is **reported to the user** and
stops there; it is never fixed on the agent's own authority.

**`[MODEL]` = inferred, observed or decided by the agent while working.** When
any `[USER]` rule conflicts with it, the `[MODEL]` rule is downgraded
automatically: the user is right. A `[MODEL]` rule becomes `[USER:<name>]`
only on the user's **explicit confirmation** — never because it looks solid,
never because it is old, never because the code has verified it.

**Nothing is ever deleted.** A rule that has become false leaves its page, but
the journal keeps every entry, the one that retired it included: the canon's
history is part of the canon.

## Who decides

Inside a framing the user validated, the agent decides by itself, applies the
choice, and records it as a decision entry, listed in its report with no answer
expected. Coming back to a decision is a new entry that replaces it, never a
"mistake": the record makes the implicit explicit, it does not point at a
fault.

What stays with the user is listed in the project's canon; by default:

- their own channel — what they set by hand in the project;
- the product's intent;
- deleting their work;
- anything irreversible or leaving the machine (push, publication, sending a
  build);
- launching a work item.

Those, the agent asks. A `[USER]` rule is never contradicted: a conflict with
one goes to the user. Only the agent that keeps the canon writes it; the
others list their decisions in their report, and it records them.

**Work size.** Small work (one scope, no open question, one verifiable
criterion, one commit) leaves **one line in the journal**. Medium and large
work (a validated framing, run by an orchestrator, with child sessions for the
large) leaves a decision entry for each choice the agents settled.

## Common operations

**Add an entry** — write one line at the end of the current month's journal
file, with the next free `CANON:n`. A point that comes from the user (stated or
validated in the conversation) → `[USER:<name> date]`. A point observed while
working → `[MODEL date]`. A `[USER]` entry carries only what the user stated or
validated: details taken from another rule or observed while working go into a
separate `[MODEL]` entry that cites it. Touch a page only if a rule in force
changes: amend that rule and add the new ID to its `Sources`, or add a rule
with a fresh ID. Never touch neighboring rules along the way.

**Record a decision** — one decision entry in the journal. When the decision
sets a lasting rule, the page carries it as a `[MODEL]` rule citing the entry.
Coming back to it: a new decision entry; the page rule is amended and cites it.

**Retire a rule** — a journal entry that names the rule that leaves (its ID or
its sources) and why; then remove the rule from its page. A `[USER]` rule is
retired only on the user's decision, recorded as a `[USER]` entry.

**Promote `[MODEL]` → `[USER:<name>]`** — only after the user's explicit
confirmation on that specific point ("yes, that's the rule"): a
`[USER:<name> YYYY-MM-DD]` journal entry records the confirmation; the page
rule is retagged `[USER:<name>]` and cites it in its `Sources`. Without
explicit confirmation: the rule stays `[MODEL]`, full stop.

**Resolve a conflict involving a `[USER]` rule** — rewrite nothing. Cite the
rules involved with their IDs, describe the contradiction precisely (with what
revealed it: code read, test run, request received), and ask the user which one
is authoritative. Until the answer comes: the `[USER]` rule takes precedence,
and the work in progress aligns with it or stops. The answer is a `[USER]`
entry. A conflict between `[MODEL]` rules only, inside a validated framing, is
settled by the agent as a decision entry.

**Initialize the canon** — if `.claude/canon/` does not exist, propose it and
create the four pages, each with only its title (`# Expectations`,
`# Conventions`, `# Tests`, `# Invariants`), and `.claude/journal/` with the
current month's `canon-YYYY-MM.md` holding only its title (git does not keep an
empty folder). **Never invent history**: no entry retroactively inferred from
the code at bootstrap time; the canon fills up as it goes.

**Migrate a v1 canon** — a work item the user launches:

1. Create `.claude/journal/`.
2. Copy each entry block — the entry line plus its continuation lines,
   malformed lines included — word for word into the journal file of its
   month (the date of its provenance), sorted by ID within each file. A block
   with no readable date goes to the month of the preceding ID and is flagged
   in the report.
3. Rewrite the pages: only the rules still in force, one line each, with fresh
   IDs, each citing every journal ID it rests on. Passing observations, dated
   measurements and retired entries stay in the journal only.
4. Every `[USER]` entry still in force (not struck) is cited by at least one
   page rule; otherwise list it for the user, with its ID and the reason.
5. Run the marketplace's validator on the project root
   (`python3 scripts/validate.py <project root>`, from a checkout of the
   marketplace) when it is available, and fix what it reports.

## Capture ritual (mandatory at the close of every task)

The scribe agent runs this ritual at the close of **every** task, before
closing anything in the roadmap, based on the conversation and the reports of
the orchestrator and of the child sessions.

1. Ask explicitly: **"what implicit point was worked out during this pass?"**
2. Go back over the conversation: each request, decision, or validation from
   the user along the way → a `[USER:<name>]` entry.
3. Go back over the work: a test command that actually works, an observed
   invariant, a pitfall encountered, a constraint discovered → a `[MODEL]`
   entry.
4. Go back over the reports: each choice an agent settled inside the framing
   → a decision entry.
5. **Journal first, then pages**: write the entries, then update every rule
   in force they change, citing the new IDs. Do it before closing the task in
   the roadmap, then remind that `.claude/canon/` and `.claude/journal/` still
   need to be committed.
6. Nothing new? Say so explicitly — that is a valid answer, not a reason to
   skip the step.

## Read gate (before any code action)

Before writing or modifying code in the project, read the relevant pages (at
minimum `invariants.md` and `conventions.md`; `tests.md` as soon as
verification is involved; `expectations.md` as soon as behavior is involved).
Open the journal only to trace a rule's source. A `[USER]` rule takes
precedence over any intuition of the model, any general habit, and any
precedent found elsewhere in the code. A `[MODEL]` rule serves as a hint, not
a law.

## Layout v1 (projects not migrated yet)

No `.claude/journal/` folder: the themed files of `.claude/canon/` hold every
entry, dated, in the journal grammar above, and the next free ID is looked up
across the folder. Nothing is deleted there either: an outdated entry is
struck through (`~~…~~`) and followed by `— obsolete YYYY-MM-DD: <reason>`; a
promoted entry keeps its ID, takes the confirmation date and ends with
`(promoted from MODEL)`. Every operation above writes one entry in the right
themed file (decision entries and the line of small work included). Propose
the migration; the user launches it.

## Guardrails

- Journal: append only — never edit, reorder or delete a written entry.
  Pages: rewritten clean, but never a renumbered or reused ID, never a rule
  without its sources.
- `[USER]` always takes precedence, over the model as over the code; its
  substance changes only through a new `[USER]` entry. Inside a validated
  framing, the agent decides what is not reserved to the user, and records it.
- A vague entry is worthless: a point that cannot be verified (exact command,
  observable behavior, applicable rule) must be reworded or asked about.
- The canon is not a logbook: no session narrative, no "I did X", only durable
  points and the decisions taken.
- Never invent canon to fill space: four nearly empty pages that are true beat
  a plausible but false canon.
