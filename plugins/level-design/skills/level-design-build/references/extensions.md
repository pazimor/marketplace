# Project extensions: `.claude/level-design/`

The plugin is generic. A project **extends it without modifying it**: its own rules, its references per scene type, its specs, its tooling and its pitfalls are declared in an index that both skills and the `level-design-reviewer` agent read.

## Where

- `.claude/level-design/index.md` at the project root — **the only entry point**.
- The project's own files live alongside it (`.claude/level-design/arena.md`, `pitfalls.md`…) or elsewhere in the repo: the index cites them by path relative to the root.

## Index grammar

Sections in this order; an empty section is omitted. Each path is followed by its role.

```markdown
# Level design — project extensions

## Context
<one paragraph: genre, number of players, movement, measured player gauge, engine, asset pack, rendering style.>

## Human expectations
- <expectation that applies to every level, with its canon ID>

## Always read
- `<path>` — <role>

## <Scene type>            (e.g. "Exterior arena", "Interior room")
- `<path>` — <role: rules, recipes, measured reference>
- <project rule for this type, with its canon ID>

## Specs
- Folder: `<path>` · naming: `<pattern>`
- Last validated spec per type: `<path>` (…)
- Recipes already measured: `<path>` — <measured reference>

## Quality control
- `<path>` — <project checklist, which takes precedence over the generic pre-flight for what it covers>

## Steps
- Step <n> (<name>) — <project-specific detail: command, tool, agent, discipline>

## Pitfalls
- `<path>` — pitfalls specific to the project's engine and assets
```

## Priority order

Project canon `[USER]` > index and the files it cites > the plugin's skills > measured references (pack demos) > intuition. When the index and the plugin diverge, the index wins; when the index and a `[USER]` entry diverge, the canon wins and the gap is reported.

## When to read it

- **Always first**: during framing (`level-design-build` step 1), before applying `level-design-taste`, and at the start of each review.
- Read `Context`, `Human expectations`, `Always read`, the section for the scene type being judged or built, then `Specs`. Read `Quality control`, `Steps` and `Pitfalls` at the step concerned.

## Resuming work already done

- **A new version of a level picks up its existing spec**: its decisions (§0) remain settled, its observed defects become §2, and its build pass is corrected instead of starting over from scratch.
- **A new level uses the last validated spec of the same type, listed in the index, as its template.**
- **A recipe already measured for the same reference is reused**: it is extended, not re-measured.
- Lessons from a session go into the canon **and**, if they are a reusable pitfall, into the pitfalls file cited by the index.

## Missing index

Look for a specs folder (`.claude/level-specs/`, `docs/**/level*`) and grep the canon for "level design", "arena", "room", "map". Offer the human to create the index with what was found; do not write it without their agreement.
