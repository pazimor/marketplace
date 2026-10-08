---
name: level-design-build
description: Procedure for building or evolving a 3D level — new arena, new map, new biome, new room, or a new version of a scene after feedback from the human ("make a new map", "v3 of the gorge", "redo this room"). Runs through framing, measured recipes from the reference, a spec with questions, a scripted and idempotent build pass, audit, screenshots, review and honest delivery. Use before writing any spec or scene build script, however small.
---

# Building a level — the procedure

This skill says **when** and **in what order**. The `level-design-taste` skill says **what is good**; the `level-design-reviewer` agent **judges**. The project's own rules (engine, tools, pitfalls, style guides) live in its canon (`.claude/canon/`) and in its **extensions** (`.claude/level-design/index.md`): when this skill and the index diverge, the index wins; when the index and a `[USER]` entry diverge, the canon wins.

## Project extensions — read first

If `.claude/level-design/index.md` exists, read it **before step 1**. It declares the game's context, the human's expectations, the references per scene type, the specs and recipes already written, the project checklist, the details of each step (tools, commands, agents) and the pitfalls file. At each step below, also apply the `Step n` line of the index. Grammar, order of precedence and resuming existing work: [references/extensions.md](references/extensions.md). No index: look for the specs and offer to create one.

## What the human always expects

- **The human decides the design.** Questions are asked **before** building, each with options (a)/(b)/(c) and a reasoned recommendation first. The answer is recorded as given in the canon (`[USER]`), then we build without asking again.
- **We build, the human walks through it.** They say what bothers them; they do not place things on our behalf. **Their manual tweaks are sacred**: the pass preserves them.
- **One scripted, idempotent build pass per scene.** Replayed N times: same result, zero duplicates, and the 2nd run reports "nothing to do". Overwriting lives in a separate command, marked dangerous, that only the human triggers.
- **Quality over speed.** We judge the screenshots ourselves and redo the work rather than show a weak render.
- Nothing is committed or pushed: the working tree goes back to the human.

## The steps

Steps marked ⏸ are stops: we wait for the human. "Capable agent" means the most capable model available; if an orchestrator delegates, it picks according to the note in parentheses on each step.

1. **Framing** (orchestration) — re-read this skill, the extensions index, `level-design-taste`, the canon entries of the domain since the last delivered scene, and the roadmap line. **List the existing specs and recipes** (the `Specs` section of the index): a new version reuses its spec; a new level takes the last validated spec of the same type. Record the human's intent as a `[USER]` entry, as they state it. Write the **Level reading** (`level-design-taste` §0.B).

2. **Recipes from the reference** (capable agent, read-only) — measure the closest reference scene (asset pack demo, already validated level) **at the source**: numbers, not impressions. Method: [references/recipes.md](references/recipes.md). Deliverable: a recipes file next to the project's specs. A recipe already measured for the same reference is completed, not redone.

3. **Spec** (same agent) — template: [references/spec.md](references/spec.md). Numbered requirements, defaults not to reproduce, what is already measured, intent, **three dimensioned layout concepts**, modularity, living environment, objective/lighting/budget, pass, **questions**, DoD. Model: the last validated spec of the same type in the project. **New version**: update the existing spec (decisions already made in §0, defects found in §2) instead of writing a new one.

4. ⏸ **Questions for the human** — relayed plainly, short, recommendation first. The most structuring ones first; ≈ 10 to 18 for a new level. The human approves in bulk or answers point by point. Answers are recorded as `[USER]` entries (mark "interp." whatever is interpreted) and copied at the top of the spec (§ Decisions). An undecided point stays listed as pending: we do not decide on the human's behalf.

5. **Code prerequisites** (capable agent) — what the scene requires and the runtime does not provide (new object types, replication, safe points…). Serialized contracts are additive only (never reorder a list that feeds a seeded draw). Green compilation before continuing.

6. **Build pass** (capable agent) — one script per scene, numbered commands (`1 — Build`, `2 — Audit`…), with no blocking dialog, idempotent, with:
   - **fingerprint** of created objects: an object whose placement has changed since creation is a human adjustment → preserved, named in the log, never overwritten; new scenery goes into a new group;
   - **exposed settings** as visible, movable markers (anchors, pivots, floors), never hard-coded;
   - **built-in audits**, read-only ([level-design-taste/references/audits.md](../level-design-taste/references/audits.md));
   - **named capture cameras** that persist, set up like the player camera.
   For a modular kit: a declarative description (layout) + a deterministic builder that **rejects an invalid layout as a whole** with a named message.

7. **Play** (engine operator agent) — each command run **twice** (the 2nd run = "nothing to do"), audit, screenshots, then the level **played**: make sure you can stand on every surface, test every fall, every mode. Short play sessions. An object that only exists at runtime is absent from screenshots taken outside play.

8. **Judgment** — the orchestration itself reviews the screenshots at full resolution, then the `level-design-reviewer` agent with the spec. Run through the entire pre-flight of `level-design-taste` §8, then the project checklist cited by the index. Severity scale: blocking > major > minor; a severity is only addressed once the previous one is empty. If the result is weak, return to step 6 **before** showing it.

9. ⏸ **Delivery** — an honest result: what works (measured), what remains (measured), what could **not** be verified and why. The human walks through it; their feedback → canon `[USER]` → new version via step 6 (mode: `level-design-taste` §6).

## Keeping the procedure up to date

Every new lesson → a dated entry in the project canon **and**, if it is a reusable pitfall, a line in the pitfalls file cited by the index. A project-specific rule that comes back on every level goes into the index or the scene-type file it cites, never into this plugin. The generic pitfalls already learned the hard way are in [references/pitfalls.md](references/pitfalls.md): read them before writing the pass.

## Guardrails

- No hand placement by the agent in the human's scene: everything goes through the pass. When the human adjusts something, the adjustment is carried into the script or preserved by the fingerprint.
- A pass that does not converge (two criteria making an object oscillate) is a bug, not a setting.
- Never validate on out-of-engine tests alone: the check inside the engine finds what the prototype does not see.
- Validate **one** family, **one** corner and **one** junction on screen before generalizing. Generating too much and looking too little is the typical failure.
- Never blindly re-run a history command from an engine-driving tool: its context has changed.
