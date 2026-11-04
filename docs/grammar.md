# Formal grammar — canon and roadmap

This document **describes** the grammar defined by the two skills of the `orchestration` plugin.
It invents no variant of its own: the SKILL.md files alone own the grammar (`CANON:2`). If this
document and a SKILL.md differ, the SKILL.md prevails and this document must be corrected.

- Canon: `plugins/orchestration/skills/canon-tracker/SKILL.md`, § "Where the canon lives",
  § "Entry grammar", § "Provenance", § "Common operations".
- Roadmap: `plugins/orchestration/skills/roadmap-tracker/SKILL.md`, § "Where the roadmap lives",
  § "File grammar" (block "File structure" + "Conventions"), § "Common operations".

The executable validator is `scripts/validate.py` (python3 stdlib, no dependency, no network call):

```sh
python3 scripts/validate.py [ROOT] [--strict]     # ROOT by default: .
python3 -m unittest discover -s scripts/tests -v    # validator tests
```

Output: one line per finding, `ERROR|WARN <file>:<line>: [<code>] <message>`, then a summary. Exit
code `0` with no error, `1` with at least one error (or a warning under `--strict`), `2` if the root
does not exist. Each missing part (manifests, canon, roadmap) is simply skipped, which makes the
script usable on any project that uses the plugin.

**Two layouts.** The validator checks the **v1 layout** (sections 1 and 2: canon entries with dated
provenance in `.claude/canon/`, a single `.claude/roadmap.md`) unless the project has a
`.claude/journal/` folder, in which case it checks the **v2 layout** (section 5). The layout switch is
described in § 5.1; the v1 part below is unchanged by it. Manifests and frontmatter (section 3) apply
in both layouts.

The **Level** columns below distinguish what violates a rule written in a SKILL.md (`ERROR`) from
what is only suspect or falls under an unsettled reading (`WARN`).

## Notation

Simplified ISO EBNF: `=` defines, `,` concatenates, `|` alternates, `[ … ]` optional, `{ … }` zero or
more, `"…"` literal, `? … ?` informal description. `SP` is a space, `NL` a line break, `INDENT` one or
more spaces or tabs at the start of a line.

```ebnf
digit      = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;
number     = digit , { digit } ;
date       = digit , digit , digit , digit , "-" , digit , digit , "-" , digit , digit ;
             (* YYYY-MM-DD, and a real calendar date *)
text       = ? one or more characters, excluding end of line ? ;
blank-line = { SP } , NL ;
```

---

## 1. Canon — `.claude/canon/*.md` (v1 layout)

Source: canon-tracker, § "Where the canon lives" and § "Entry grammar".

### 1.1 Location

- A `.claude/canon/` folder at the root of the repo, one **theme per file** `*.md` (`expectations.md`,
  `conventions.md`, `tests.md`, `invariants.md`, plus any clearly distinct theme).
- **Never a `misc.md`** (§ "Where the canon lives").

### 1.2 File

```ebnf
canon-file   = { blank-line } , title-line , { blank-line | entry | heading-line } ;
title-line   = "# " , text , NL ;                 (* "# Tests", "# Invariants"… *)
heading-line = "#" , { "#" } , SP , text , NL ;   (* tolerated, see ambiguous point A3 *)
entry        = "- " , entry-body , NL , { continuation } ;
continuation = INDENT , text , NL ;               (* wrapped line, or "— obsolete" line *)
```

An entry fits on one logical line: the `- …` line and its indented continuation lines, joined by a
space. A blank line ends the entry. **Any non-empty line that is neither a title, an entry, nor a
continuation is floating prose, which is forbidden** ("Never floating prose, never a paragraph
outside an entry").

### 1.3 Entry

```ebnf
entry-body   = live-entry | struck-entry | struck-point ;

live-entry   = head , SP , point ;
head         = "`CANON:" , number , "`" , SP , provenance ;
provenance   = "[USER:" , name , SP , date , "]"
             | "[MODEL" , SP , date , "]" ;
name         = ? non-empty text without "]", with no leading or trailing space ? ;
point        = text , [ SP , "(promoted from MODEL)" ] ;   (* promotion: USER only *)

(* Deprecation — two accepted readings, see ambiguous point A1 *)
struck-entry = "~~" , live-entry , "~~" , obsolete-tail ;          (* form of the example *)
struck-point = head , SP , "~~" , point , "~~" , obsolete-tail ;   (* "strike through the text" *)
obsolete-tail = SP , obsolete | NL , INDENT , obsolete ;             (* end of line or below *)
obsolete     = "— obsolete" , SP , date , [ SP ] , ":" , SP , reason ;   (* written without the space *)
reason       = text ;   (* may cite the replacing ID, e.g. "replaced by `CANON:12`" *)
```

Accepted example (long struck entry, `— obsolete` line below it):

```markdown
- ~~`CANON:7` [MODEL 2026-07-02] The tests run via `make test`, from the repository root, once the fixtures are regenerated…~~
  — obsolete 2026-08-14: `make test` was removed, replaced by `CANON:12`.
```

### 1.4 Checked rules

| Code | Level | Rule | Source (canon-tracker) |
|---|---|---|---|
| `canon.title` | ERROR | The file starts with `# <Theme>` | § "Initialize the canon" |
| `canon.prose` | ERROR | No line outside an entry | § "Entry grammar" |
| `canon.entry` | ERROR | Entry conforms to `entry-body` (ID in backticks, provenance `[USER:<name> date]` or `[MODEL date]`, non-empty point) | § "Entry grammar" |
| `canon.date` | ERROR | Valid calendar dates | § "Entry grammar" |
| `canon.duplicate-id` | ERROR | `CANON:n` unique **across the whole folder**, struck entries included (never reused) | § "Entry grammar" |
| `canon.strike` | ERROR | Opening `~~` closed; no partial `~~` in the middle of a point | § "Deprecate an entry" |
| `canon.obsolete-missing` | ERROR | A struck entry carries `— obsolete YYYY-MM-DD: <reason>` | § "Deprecate an entry" |
| `canon.obsolete-unstruck` | ERROR | An `— obsolete` mark appears only on a struck entry | § "Deprecate an entry" |
| `canon.promotion` | ERROR | `(promoted from MODEL)` only on a `[USER:…]` entry | § "Promote" |
| `canon.misc` | ERROR | No `misc.md` | § "Where the canon lives" |
| `canon.obsolete-before-entry` | WARN | Obsolescence date ≥ entry date | — (consistency) |
| `canon.unknown-ref` | WARN | A `CANON:n` cited in an entry exists | — (consistency) |

Out of the validator's reach (not decidable mechanically): "one sentence, two at most", the
legitimacy of a `[USER]` provenance, choosing the right thematic file, whether an entry is "durable".

---

## 2. Roadmap — `.claude/roadmap.md` (v1 layout)

Source: roadmap-tracker, § "File grammar". The validator reads the **versioned mirror**
`.claude/roadmap.md` (the source in auto-memory, `~/.claude/projects/<project>/memory/roadmap.md`, is
outside the repo and is an identical copy of it, § "Where the roadmap lives").

### 2.1 File

```ebnf
roadmap-file    = { blank-line } , "# Roadmap" , NL , { section } ;
section         = specs-section | milestone-section | backlog-section ;

specs-section   = "## Specs" , NL , { blank-line | spec } , [ rules ] ;
spec            = "- " , spec-id , SP , "**" , text , "**" , SP , "[" , spec-status , "]" , NL ,
                  { continuation } ;           (* with an expected "- Canon: …" sub-bullet *)
spec-status     = "draft" | "active" | "retired" ;
rules           = "Rules:" , NL , { "- " , text , NL , { continuation } | blank-line } ;

milestone-section = "## M" , number , " — " , text ,
                    " (`ROADMAP:MILESTONE:" , number , "`, " , ms-status , ")" , NL ,
                    { blank-line | description-line | dod-line | task } ;
ms-status       = "planned" | "active" | "done" ;
description-line = text , NL ;                 (* free prose, dated decisions *)
dod-line        = "Milestone DoD:" , SP , text , NL ;

backlog-section = "## Backlog (no milestone)" , NL , { blank-line | task } ;
```

### 2.2 Task

```ebnf
task        = "- [" , box , "] " , task-id , SP , title , [ SP , suffix ] , [ trailer ] , NL ,
              { continuation } ;
box         = " " | "~" | "x" ;                (* todo · in_progress · done *)
title       = [ prefix , SP ] , text ;
prefix      = "[BUG]" | "[PLACEHOLDER]" | "[RECURRING]" | "[BACKGROUND]" | "[RESEARCH]" ;
suffix      = "_(" , part , { "; " , part } , ")_" ;
part        = "implements " , spec-id , { ", " , spec-id }
            | "depends on " , task-id-ref , { ", " , task-id-ref }
            | "claimed by " , text
            | "blocked: " , text ;             (* always last: may contain ";" *)
trailer     = SP , text ;                      (* dated annotation after the suffix, see A5 *)

spec-id     = "`ROADMAP:SPEC:" , number , "`" | "ROADMAP:SPEC:" , number ;
                                               (* with backticks at the head of a spec, without them in the suffix *)
task-id     = "`ROADMAP:TASK:" , number , "`" ;
task-id-ref = "ROADMAP:TASK:" , number ;
```

Each suffix element appears at most once, **in this order**: `implements`, `depends on`, `claimed by`,
`blocked:` (§ "Conventions").

### 2.3 Checked rules

| Code | Level | Rule | Source (roadmap-tracker) |
|---|---|---|---|
| `roadmap.title` | ERROR | First title `# Roadmap` | "File structure" |
| `roadmap.section` | ERROR | Sections `## Specs`, `## M<n> — …`, `## Backlog (no milestone)` only | "File structure" |
| `roadmap.spec` | ERROR | Spec conforms, status `draft|active|retired`; no free bullet before `Rules:` | "File structure" |
| `roadmap.milestone` | ERROR | Milestone heading conforms, status `planned|active|done` | "File structure" |
| `roadmap.task` / `roadmap.checkbox` | ERROR | Task conforms, box `[ ]`, `[~]` or `[x]` | "Conventions" |
| `roadmap.duplicate-id` | ERROR | IDs unique **per family** (SPEC, MILESTONE, TASK) | "Three families of stable IDs" |
| `roadmap.suffix` / `roadmap.suffix-order` / `roadmap.suffix-id` | ERROR | Suffix `_( … )_`: known elements, enforced order, full IDs of the right family | "Conventions" |
| `roadmap.unknown-ref` | ERROR | `implements` → existing spec; `depends on` → existing task | "Add a spec / a milestone / a task" |
| `roadmap.self-dependency` / `roadmap.dependency-cycle` | ERROR | No circular dependency (a task in the cycle would never be unblocked) | "Claim a task" |
| `roadmap.claim-missing` | ERROR | `[~]` carries `claimed by <user>` **or** `blocked: <reason>` | "Conventions", see A4 |
| `roadmap.claim-on-done` | ERROR | `[x]` no longer carries `claimed by` | "Complete a task" |
| `roadmap.milestone-done` | ERROR | Milestone `done` ⇒ all its tasks `[x]` | "Conventions" |
| `roadmap.dependency-not-done` | WARN | Task `[~]`/`[x]` with a dependency that is not `[x]` | "Claim a task", see A6 |
| `roadmap.claim-on-todo` | WARN | `[ ]` with `claimed by` | "Conventions" |
| `roadmap.blocked-not-in-progress` | WARN | `blocked:` outside `[~]` | "Conventions" |
| `roadmap.title-prefix` | WARN | Bracketed title prefix outside the normalized list | "Conventions" |
| `roadmap.milestone-dod` | WARN | Milestone without a `Milestone DoD:` line | "File structure" |
| `roadmap.milestone-number` | WARN | `M<k>` ≠ `ROADMAP:MILESTONE:<k>` | "File structure" (example) |
| `roadmap.spec-canon` | WARN | Spec without a `- Canon: …` sub-bullet | "File structure" |
| `roadmap.bullet` | WARN | Non-task bullet in a milestone or the backlog | "File structure" |
| `roadmap.unknown-canon-ref` | WARN | A `CANON:n` cited exists in `.claude/canon/` | — (consistency) |

---

## 3. Manifests and frontmatter (marketplace only)

These apply only to the marketplace repo; they are ignored elsewhere.

| Code | Level | Rule |
|---|---|---|
| `manifest.json` | ERROR | `.claude-plugin/marketplace.json` and each `plugins/*/.claude-plugin/plugin.json` load as JSON (`CANON:3`) |
| `manifest.plugin-name` / `manifest.plugin-version` | ERROR | `plugin.json`: `name` non-empty, `version` semver 2.0 |
| `manifest.marketplace-*` | ERROR | `marketplace.json`: `name`, `owner.name`, `plugins[]` with `name` + `source`; `version` semver if present; local source as `./…` containing a `plugin.json` |
| `manifest.name-mismatch` / `manifest.version-mismatch` | ERROR | Name (and version, if the catalog entry carries one) of the catalog entry = those of the `plugin.json` it points to |
| `manifest.unlisted-plugin` | WARN | Plugin under `plugins/` missing from the catalog |
| `frontmatter.syntax` | ERROR | `plugins/*/agents/*.md` and `plugins/*/skills/*/SKILL.md` start with a readable `---` … `---` frontmatter |
| `frontmatter.name` / `frontmatter.description` | ERROR | Fields present and non-empty |
| `frontmatter.model` | ERROR | `model` ∈ {`opus`, `sonnet`, `haiku`, `fable`, `inherit`} or a `claude-*` ID |
| `plugin.model-mention` | ERROR | Model name (`opus`, `sonnet`, `haiku`, `fable`, whole word, case ignored) in a `.md` or `.json` under `plugins/`, outside the `model:` line of an agent's frontmatter (`CANON:22`) |
| `plugin.launch-separator` | ERROR | A `claude --bg` command (inline code or fenced block) in a `.md` under `plugins/` puts `--` after its last list option (`--disallowedTools`, `--allowedTools`, `--add-dir`, `--tools`, `--mcp-config`, `--betas`, `--file`): otherwise that option takes the prompt and the session starts idle (`CANON:68`) |
| `frontmatter.effort` | ERROR | `effort` ∈ {`low`, `medium`, `high`, `xhigh`, `max`} (`CANON:6`) |
| `frontmatter.mascot` | WARN | `mascot` of an agent ∈ {`scribe`, `chef`, `artist`, `inspector`, `courier`, `artisan`, `scholar`, `mage`, `bare`}: mascot of the `agents-info` band, which Claude Code ignores |
| `frontmatter.plugin-agent-ignored` | WARN | `hooks`, `mcpServers`, `permissionMode` in a plugin agent: ignored by Claude Code (`CANON:6`) |
| `frontmatter.name-format` / `frontmatter.name-dir` | WARN | `name` in kebab-case; a skill's `name` = its folder name |

The frontmatter is read by a mini YAML parser (top-level keys, plain or quoted scalars, `|`/`>`
blocks, comments): enough for these files, with no dependency on PyYAML.

---

## 4. Ambiguous points in the SKILL.md files (unsettled; both readings are accepted)

- **A1 — What is struck through?** canon-tracker, § "Deprecate an entry" says "strike through the text
  (`~~…~~`)"; the example in § "Entry grammar" strikes through **the whole** entry, ID and provenance
  included. The validator accepts `~~`CANON:n` [...] point~~` and `` `CANON:n` [...] ~~point~~ ``.
- **A2 — Where does the obsolescence mark go?** "add below it or at the end of the line": both are
  accepted (indented continuation or same logical line).
- **A3 — Sub-headings in a canon file.** Nothing explicitly allows or forbids them; "never floating
  prose" targets paragraphs. Lines `#…` are tolerated.
- **A4 — Blocked task.** "`[~]` always accompanied by `claimed by`" vs "a blocked task stays `[~]` with
  `blocked:`": does `blocked:` also require `claimed by`? The validator accepts `[~]` with one **or**
  the other.
- **A5 — Text after the suffix.** The real roadmap carries dated annotations after `)_` ("— decision
  2026-09-24: retired"). The grammar does not provide for them, but "scope decisions are
  dated in the text"; they are accepted.
- **A6 — Unfinished dependency.** The claim rule ("if a dependency is not done: report it and stop")
  is an operation rule, not grammar, and the real roadmap contains exceptions decided by the user
  (TASK:10 done "in advance"): warning, not error.
- **A7 — Name in `[USER:<name>]`.** No character set is fixed; any text without `]` is accepted
  (internal spaces included).
- **A8 — Dash of the obsolescence mark.** The SKILL writes `—` (em dash); only this character is
  recognized. A `-` or `--` produces `canon.obsolete-missing`.

---

## 5. v2 layout — `.claude/journal/` present

Everything in this section applies **only** when the layout switch of § 5.1 selects v2. Sources: by
topic, since the SKILL.md sections are named by their authors: canon-tracker (page grammar, journal,
`Sources`), roadmap-tracker (open roadmap, archive, `history:` element).

### 5.1 Layout switch

```text
v2  iff  <root>/.claude/journal/  is a directory
v1  otherwise (the output is the one of the v1 validator, finding for finding, in the same order)
```

In v2, only the files named `canon-YYYY-MM.md` and `roadmap-YYYY-MM.md` **directly** in
`.claude/journal/` are read (`\d{4}-\d{2}` for the month). **Every other file there is ignored
completely**, whatever it contains: a project may keep archived notes in that folder, full of
`CANON:n` or `ROADMAP:TASK:n` strings inside fenced blocks. Nothing depends on the language of the
section titles: projects write them in any language.

```ebnf
journal-canon-name   = "canon-" , year , "-" , month , ".md" ;
journal-roadmap-name = "roadmap-" , year , "-" , month , ".md" ;
year  = digit , digit , digit , digit ;
month = digit , digit ;
```

### 5.2 Canon page — `.claude/canon/*.md`

A page holds **live rules only**, one per line, each citing the journal entries it comes from.
Nothing is struck through on a page, nothing is dated: history lives in the journal.

```ebnf
page          = { blank-line } , title-line , { blank-line | group-heading | page-rule } ;
title-line    = "# " , text , NL ;                    (* first non-blank line *)
group-heading = ( "## " | "### " ) , text , NL ;      (* any text *)
page-rule     = "- " , rule-id , SP , page-prov , SP , rule-text , SP , sources , NL ;
rule-id       = "`CANON:" , number , "`" ;
page-prov     = "[USER:" , name , "]" | "[MODEL]" ;    (* NO date; name as in v1 (A7) *)
rule-text     = ? non-empty text, on ONE line ? ;
sources       = ( "Sources:" | "Sources :" ) , SP , source-ref , { ", " , source-ref } , [ "." ] , { SP } ;
source-ref    = "`CANON:" , number , "`" ;
```

A rule is **one top-level bullet on one line**: an indented line under a rule is an error. A name that
ends with a date (`[USER:x 2026-11-04]`) or a dated `[MODEL 2026-11-04]` is not a page provenance.
`~~` and the marks `— obsolete` / `— obsolète` are forbidden anywhere on a page line.

### 5.3 Canon journal — `.claude/journal/canon-YYYY-MM.md`

The journal is tolerant: it may hold legacy content copied verbatim from a v1 canon. It is checked at
the `WARN` level only, except for its IDs.

```ebnf
journal-canon = { blank-line } , [ title-line ] , { blank-line | heading-line | fence | journal-entry
                | continuation | stray } ;
journal-entry = [ "- " ] , [ "~~" ] , "`CANON:" , number , "`" , text , NL ;   (* non-indented line *)
continuation  = INDENT , text , NL ;                  (* belongs to the entry just above *)
fence         = "```" , ? up to the closing fence (same or longer run of backticks) ? ;
```

- A **non-indented** line that starts an entry (`^(- )?(~~)?` + `` `CANON:n` ``) opens an entry; the
  indented lines that follow continue it; a blank line closes it. Headings (`#…`) and blank lines are
  fine. **Lines inside a fenced block are never entries** and are skipped altogether.
- Each entry block (head line + continuations joined by a space) is run through the **v1 entry
  grammar** (§ 1.3), but every violation is reported as `WARN journal.entry`, the v1 code being quoted
  in the message. Tolerated legacy shapes: struck entries with `— obsolète`, struck entries with no
  obsolete mark, an entry without its `- `, `- ~~`CANON:9` …~~` with an indented `— obsolete …` line.

### 5.4 Open roadmap — `.claude/roadmap.md`

All the checks of § 2 apply (same file grammar), plus the v2 additions below. A task closed in v2 is
**moved to the archive**, so the open roadmap holds only `[ ]` and `[~]` tasks.

```ebnf
suffix-v2  = "_(" , part-v2 , { "; " , part-v2 } , ")_" ;
part-v2    = part | history ;                          (* part: § 2.2 *)
history    = "history: " , archive-name ;               (* LAST element of the suffix *)
archive-name = journal-roadmap-name ;                   (* the file must exist in .claude/journal/ *)
```

Order of the suffix elements: `implements`, `depends on`, `claimed by`, `blocked:`, `history:`. As
`blocked:` runs to the end of the suffix, a trailing `; history: <file>` is split off from it. In the
**v1 layout**, `history:` is not a known element: it produces the usual `roadmap.suffix` error.

`depends on`, `implements` and milestone references resolve against the roadmap **and** the archive: a
dependency on a task closed in the archive is known and counts as done (no unknown-reference error, no
"dependency not done" warning); spec and milestone IDs that appear in the archive are known. `CANON:n`
references in the roadmap resolve against the pages and the journal.

### 5.5 Roadmap archive — `.claude/journal/roadmap-YYYY-MM.md`

The archive is **verbatim legacy content**; its section titles are free (any language). Only the
**top-level** lines below are classified, **by checkbox alone**, outside fenced blocks:

```ebnf
archive-task = "- [" , box , "] `ROADMAP:TASK:" , number , "`" , text , NL ;   (* at column 0 *)
(* box "x"        : the task is closed here
   box " " or "~" : history line of a task that is still open in the roadmap
   any other box  : ignored *)
```

Everything else is tolerated silently (headings, prose, milestone blocks, spec lines, indented lines),
but every `ROADMAP:SPEC:n` / `ROADMAP:MILESTONE:n` found outside a fence makes that ID known.

### 5.6 Checked rules (v2)

| Code | Level | Rule | Source |
|---|---|---|---|
| `canon.title` | ERROR | A page starts with `# <title>` | canon-tracker, page grammar |
| `canon.prose` | ERROR | On a page, only blank lines, `#`/`##`/`###` headings and rules | canon-tracker, page grammar |
| `canon.page-rule` | ERROR | A rule is one bullet on one line, `` `CANON:n` ``, `[USER:<name>]` or `[MODEL]` without date, non-empty text; no indented continuation | canon-tracker, page grammar |
| `canon.page-sources` | ERROR | A rule ends with `Sources:` / `Sources :` and one or more `` `CANON:n` `` separated by `, `, optional final `.` | canon-tracker, page grammar |
| `canon.page-strike` | ERROR | No `~~` and no `— obsolete` / `— obsolète` on a page line | canon-tracker, page grammar |
| `canon.misc` | ERROR | No `misc.md` | canon-tracker, where the canon lives |
| `canon.duplicate-id` | ERROR | `CANON:n` unique across pages **and** journal (page↔journal, page↔page, journal↔journal, across months) | canon-tracker, IDs |
| `canon.unknown-source` | ERROR | Every ID cited in `Sources` is an entry of the journal (not a page rule, not absent) | canon-tracker, `Sources` |
| `canon.page-size` | WARN | Page over 40960 bytes (a project's canon may set another budget) | canon-tracker, page budget |
| `canon.unknown-ref` | WARN | A `CANON:n` cited in a rule text (before `Sources`) or in a journal entry exists in pages + journal | — (consistency) |
| `journal.title` | WARN | A journal file starts with `# <title>` | canon-tracker, journal |
| `journal.prose` | WARN | Journal lines outside entries, headings, blank lines and fenced blocks | canon-tracker, journal |
| `journal.entry` | WARN | An entry block breaks the v1 entry grammar (v1 code in the message) | canon-tracker, journal |
| `roadmap.done-task` | ERROR | No `[x]` task in the open roadmap: closed tasks live in the archive | roadmap-tracker, archive |
| `roadmap.history` | ERROR | `history: <file>`: name `roadmap-YYYY-MM.md`, file present in `.claude/journal/` | roadmap-tracker, archive |
| `roadmap.closed-and-open` | ERROR | A task closed in the archive is not open in the roadmap | roadmap-tracker, archive |
| `roadmap.closed-twice` | ERROR | A task is closed once (same or different archive files; a `[x]` left in the roadmap counts) | roadmap-tracker, archive |
| `roadmap.history-not-open` | ERROR | A history line (`[ ]`, `[~]` in the archive) targets a task open in the roadmap (not closed, not absent); history lines may repeat for the same ID | roadmap-tracker, archive |
| `roadmap.done-milestone` | WARN | Milestone `done` in the open roadmap belongs in the archive | roadmap-tracker, archive |
| `roadmap.retired-spec` | WARN | Spec `[retired]` in the open roadmap belongs in the archive | roadmap-tracker, archive |

The v1 roadmap codes of § 2.3 keep their level in v2, with two changes of resolution: `roadmap.unknown-ref`
and `roadmap.dependency-not-done` consult the archive (§ 5.4), and `roadmap.unknown-canon-ref` resolves
against pages + journal. The v1 canon codes of § 1.4 are not raised in v2 on pages (replaced by the
`canon.page-*` codes) and only surface in the journal as `journal.entry`; `canon.title`, `canon.prose`,
`canon.misc`, `canon.duplicate-id` and `canon.unknown-ref` keep their names with the v2 meaning above.

### 5.7 Out of the validator's reach

- That a page rule is a faithful summary of the journal entries it cites, and that the cited entries
  are the right ones; that a rule was not silently dropped from a page.
- That a journal entry's provenance is legitimate; that a retired entry was moved to the right month.
- That the archive was filled completely, and that a history line is useful; the archive is read by
  checkbox only, so a mistyped box (`[X]`) is ignored without a finding.
- The size budget of the journal and of the archive (only pages are measured), and any budget another
  project sets for its pages.
- Every rule of § 1.4 and § 2.3 that was already out of reach in v1 (one sentence per entry, durable
  entries, the right thematic file…).
