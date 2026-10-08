---
name: level-design-taste
description: Anti-defect taste for 3D level design — arena, map, biome, room, corridor, level, blockout, set dressing or lighting of a playable scene. Read the brief, set four dials, ban the AI reflexes (square outline, slab floor, sprinkled props, carpet of lamps, rainbow of hues) and run a measurable pre-flight checklist before showing anything. Use whenever a level has to be designed, built, dressed, lit, critiqued or evolved, even if the words "level design" are never spoken.
---

# 3D level design — taste, written down

> Arenas, outdoor maps, indoor rooms and corridors, new versions of an existing level. Not menus, not UI, not gameplay code.
> Every rule below is **contextual**: read the brief first, then apply only what fits.

An LLM building a 3D scene has reflexes: a rectangular outline, a flat slab floor, props sprinkled evenly, a lamp everywhere, six hues that shout, an empty center, and "delivered" as soon as the script runs without errors. This skill exists to break them.

**Source hierarchy, always**: the project canon `[USER]` > the project extensions (`.claude/level-design/index.md` and the files it cites) > the level spec > this skill > measured references (demos from the asset pack) > your own intuition.

**Before applying anything here**:
1. If `.claude/level-design/index.md` exists, read it, then its sections `Context`, `Human expectations`, `Always read` and the one for the current scene type (grammar: `level-design-build/references/extensions.md`). Its rules complement and replace yours.
2. If the project keeps a canon (`.claude/canon/`), read its entries on scenery, light, color, maps. The figures in this skill are **starting values** measured on a real project: the project canon replaces them as soon as it sets others.

References to load, depending on the case:

| You are working on… | Also read |
|---|---|
| An arena or an outdoor map | [references/exterior.md](references/exterior.md) |
| A room, a corridor, an interior | [references/interior.md](references/interior.md) |
| Lighting, fog, color, density, depth (always useful) | [references/rendering.md](references/rendering.md) |
| An automatic audit to write or read | [references/audits.md](references/audits.md) |
| The project's own rules | The project's `.claude/level-design/index.md`, if it exists |

For the **procedure** (spec, questions, build pass, screenshots, delivery), use the `level-design-build` skill. To **judge** screenshots, use the `level-design-reviewer` agent.

---

## 0. Reading the brief (before anything else)

### 0.A The signals to read first
1. **Scene type** — combat arena, defense arena, crossing, hub, room, corridor, linear level, new version of an existing scene.
2. **Players** — how many (solo, co-op 2–6, PvP), how they move (walk, sprint, jump, vehicle, flight), their **measured** player gauge (height, radius, speed). Every scale follows from it.
3. **Enemies** — where they come from, how many at most, at what range they shoot. The engagement range sets the spacing between cover.
4. **Mood words** — "desolate", "industrial", "alive", "oppressive", "airy", "hostile planet", "clean station", "jury-rigged".
5. **References** — a demo scene from the asset pack, a game cited, a sketch, an intent plan given by the human. A human's intent plan is the starting point, not a suggestion.
6. **Silent constraints** — render budget, platform, network (what must be replicated), save data, IDs referenced by code. They take precedence over aesthetics.

### 0.B Write a one-line "Level reading" before producing anything
> **"I read this as: \<scene type> for \<players / mode>, in a \<mood words> atmosphere, relying on \<measured reference>. Dials O/D/R/N = x/x/x/x."**

Examples:
- *"I read this as: defense arena for 2–6 co-op players around an object to protect, in a desolate mining-planet atmosphere, relying on the desert demo from the pack. Dials O/D/R/N = 7/4/6/8."*
- *"I read this as: station corridor between two combat rooms, clean and cold atmosphere, relying on the interior demo from the pack. Dials O/D/R/N = 2/5/2/1."*

### 0.C Ambiguous brief: one question, not a questionnaire
If the readings truly diverge (open arena or walled valley?), ask **one** question with options (a)/(b)/(c) and your recommendation first. If you can infer, do not ask: state your reading and move on. Long series of questions belong to the spec (skill `level-design-build`), not to the conversation.

### 0.D Anti-default discipline
**Never** start from: a rectangle, a flat floor, a grid of cover, a lamp at every step, a rainbow palette, an empty center, scenery copied as-is from the demo. These are the model's reflexes. Deliberately set them aside based on the level reading.

---

## 1. The four dials

After the level reading, set four dials. Every shape, density and relief decision below depends on them. Do not invent them under other names.

* **`OPENNESS`** — 1 = scripted corridor, a single route · 10 = open arena, all directions.
* **`DENSITY`** — 1 = bare ground, maximum breathing room · 10 = cluttered, cover everywhere.
* **`RELIEF`** — 1 = flat · 10 = strong verticality (ridges, stacked levels, chasms).
* **`NATURE`** — 1 = grid-based orthogonal construction · 10 = organic, nothing plumb.

There is no universal default value: a station level and a planet arena have nothing in common. Start from the closest preset, then adjust.

### 1.A From mood words to dials
| Signal | OPENNESS | DENSITY | RELIEF | NATURE |
|---|---|---|---|---|
| "airy / hangar / large space" | 7–9 | 2–3 | 2–4 | depends on the place |
| "oppressive / stifling / labyrinth" | 2–4 | 6–8 | 3–5 | depends on the place |
| "desolate / hostile planet / wasteland" | 7–8 | 3–4 | 6–8 | 8–9 |
| "industrial / factory / refinery" | 5–6 | 5–7 | 4–6 | 3–4 |
| "jury-rigged / camp / colony" | 6 | 5–6 | 4–5 | 5–6 |
| "clean station / spaceship" | 2–3 | 4–5 | 2 | 1–2 |
| "lively / animated" | does not change the dials: living scenery **outside** the playable zone (§3.F) |

### 1.B Presets by scene type
| Scene type | OPENNESS | DENSITY | RELIEF | NATURE |
|---|---|---|---|---|
| Defense arena (object to protect) | 7 | 4 | 5 | depends on biome |
| Combat arena (waves, no object) | 8 | 5 | 6 | depends on biome |
| Crossing / exploration | 4 | 3 | 7 | 8 |
| Hub, social area | 6 | 3 | 2 | 3 |
| Interior corridor | 1–2 | 4 | 1 | 1 |
| Interior combat room | 4 | 6 | 3 | 2 |
| New version — touch-ups | = existing | = existing | = existing | = existing |
| New version — overhaul | to be discussed with the human | | | |

### 1.C What each dial drives
- **OPENNESS** → outline shape, number of routes between two points, length of sight lines, width of bottlenecks.
- **DENSITY** → props per m², share of bare ground in frame, spacing between cover, measured obstruction of the areas that "block the view".
- **RELIEF** → terrain amplitude, share of slopes > 10°, number of walkable levels, number of fall hazards.
- **NATURE** → share of free placement versus grid placement, tilting and sinking of organic pieces, curvature of edges.

---

## 2. The two placement grammars

The eye tells the artificial from the natural **before** reading the shapes. Two grammars, which never mix on the same object:

- **Structure** (walls, floors, ceilings, buildings, modules) — on the project grid, rotation in 90° steps, scale exactly 1, pivots on the grid. Target conformity ≥ 99%, named exceptions.
- **Set dressing and nature** (props, rocks, vegetation, debris) — off-grid, free yaw, scale in steps (≈ 3 sizes per species, not continuous), mirroring allowed. **Nothing organic is plumb**: rocks tilted, squashed, sunk.
- **Built structures in an open world**: place the structure on a plinth or platform that sets the joins, never a module stuck onto a slope. The ground/structure junction is hidden by debris scattered along the boundary and by shadow, not by extra masonry.
- **Repetition with motivated variation**: a run of walls is uniform; a variant enters as a **cluster** at a justified spot (service bay, access, focal point). Never mechanical A/B/A/B alternation. One "beat": 3–5 rhythmic elements, only one different.
- **Remarkable piece, one of a kind.** 2–4 for a doubled function. Beyond that, it is filler, not a landmark.

---

## 3. Directives (bias correction)

### 3.A Shape and outline
- An area is not a shape. "N × N modules" gives a **surface**; the outline is **organic**: lobes, coves, bottlenecks, isthmuses. Longest straight edge ≤ ~24 × the player's height.
- Boundaries must read as **terrain or architecture** (embankment, cliff, overhang, basin), never as a lone invisible wall or a geometric outline. Placing the playable zone in a depression helps.
- Part of the footprint may stay non-playable (transition, view) if it reads as such.

### 3.B Ground and relief
- **Never "everything sits on slabs".** Continuous, organic ground; gameplay platforms are carved out of the ground, with no visible step (height difference below the controller's step height).
- Never flat everywhere: start from a noise base (Perlin or equivalent), then **flatten what must be flat** (liquids, built zones, squares). Add the relief **after** the platforms, otherwise their fades erase it.
- AI over-flattens: count the share of flattened ground. If the platforms eat the plain, the relief is gone.
- Walkable slope: ≥ 99% of the walkable ground lies under the controller's max slope; yet the relief must **read** (measured share of slopes > 10%, see `references/audits.md`).

### 3.C Edges, drops, liquids
- Chasms, lakes, pits: **few pieces**, curved pieces at the edge, in an overlapping **chain**, and the ground modified **under** the chain. Never isolated pieces placed on ground that is left untouched.
- A curved cliff piece = edge of a chasm or ravine. Nowhere else.
- Zero shoreline gaps, zero floating rocks: this is **measured** (radii), not judged.
- Every fall has a consequence decided by the human (death, rescue, penalty) and a safety net under **each** fall. A drop threshold is signaled by its **shape** (chevrons, edge) or by a color whose role is "danger", never by the "interactive" color.

### 3.D Composition
- **One single focal point per field of view.** Two things that shout means none.
- Props in **clusters that tell a function** (3–5 objects packed together: repair station, camp, stock). Sprinkled, they are noise. Target: ≈ 90% of props in clusters.
- **The center breathes, the clusters lean against the edges.** The emptiness around the focal point is intended. But beware the opposite: an open center with no cover is a "shooting gallery".
- **Depth planes**: foreground, midground, distance in silhouette. See `references/rendering.md` for the mechanisms (distance shells, fog, distant repetition).
- **Logic of the place**: the scenery tells a story (cannons facing the base, the drill rig over the pit, pipes running to the pump). A network (pipes, cables, rails) has **no free end**: every end terminates at a wall, a tank, the ground or an elbow.

### 3.E Color and light (summary, details in `references/rendering.md`)
- **Color budget**: 1 dominant + 1 complementary + 2 accents at most. Beyond that, it is a defect.
- **One color = one role**, and only one (e.g. red = danger/enemy, cyan = interactive). The circulation plane stays calm; large flat areas of color go far away or up high.
- **The objective is the only hot spot** of color in the scene.
- **Light hierarchy**: the ambience lights, a few sources guide. No carpet of lamps. An emissive surface lights nothing: it reads as a line.
- **No clipped white**; luminance measured on the screenshot, not estimated.
- **A demo's colors are not a recipe**: they are validated with the human.

### 3.F Distant and living scenery
- The off-map area is **alive** (vehicles, ships, machines, debris) but **never encroaches** on the playable zone: no peak inside the playable envelope plus margin.
- Anything announced as visible (a base, a landmark) **must be seen** from the play zone, not behind a ledge or drowned in fog.
- Living scenery never steals the camera, never fires at players, is never exploited by enemies. If it becomes gameplay, it changes status (replication, rules).
- **No model used as an enemy is placed in the scenery.** Guaranteed confusion in play.

### 3.G Circulation and combat
- The player understands **where to move, where to take cover, and where enemies come from**, without signage.
- Passage width derived from the player gauge and the number of players: for 2–6 players, main corridors 8–15 player diameters, never < 6. A pinch point is a defect only if players are **forced** through it (no short detour).
- Cover **within the enemies' engagement range** across every open combat zone; 2–3 clusters of cover near the objective.
- No hole or hazard near the objective, the entrance, or the bottlenecks.
- The objective is recognizable **from afar and from the entrance** (order of magnitude: 5–7 × the player's height).
- Each zone has **a short name and a visible landmark**: players must be able to orient themselves by voice in co-op ("at the drill rig", "lake side").

### 3.H Scale
- Every dimension derives from the **measured** player gauge (height, radius, jump, speed). A crossing is measured in seconds of running, not only in units of length.
- Convey the scale of the world: a familiar prop enlarged in the distance, mid-sized objects on the ridges, **a single** vertical element per district.
- Judge a gameplay scene at the in-game FOV (55–65), never at the poster FOV.

---

## 4. AI tells (banned unless explicitly requested)

### 4.A Shape
* **No square or rectangular outline** readable from above.
* **No flat ground everywhere**, nor a floor paved with slabs.
* **No flat platforms under every gameplay spot** (the plain disappears).
* **No lone invisible wall** as a boundary.
* **No perfect symmetry** in an arena, unless a competitive mode requires it.

### 4.B Placement
* **No props sprinkled** evenly; no lone crate in the middle of a lane.
* **No cover aligned on a regular grid**.
* **No plumb organic element** (upright rock, perfect vertical tree repeated in a series).
* **No piece floating**, interpenetrating for no reason, or stopping in mid-air (staircase, bridge, pipe, ground edge).
* **No stretched piece**: never stretch a detail, a bevel or a pattern; only flat strips designed for it may stretch.
* **No door or window at the free end of a wall**, in a corner, or against a single wall.
* **No stacking of two full walls** to make a tall wall: base + n × shaft + cap.
* **No network with free ends** (pipe, cable, rail stopping in mid-air).

### 4.C Rendering
* **No carpet of lamps**: the ambience lights, the lamps guide.
* **No emissive surface clipping** to white; no neon signs faked with lights.
* **No rainbow palette**: count the hues.
* **No color with two roles** (the red of "danger" does not decorate).
* **No demo colors copied** without the human's validation.
* **No material from another biome** left at default on a piece.
* **No spectacular sky** that kills the silhouettes.

### 4.D Content and readability
* **No numbers, labels or danger lines** on the ground that the human did not ask for.
* **No enemy model in the scenery.**
* **No distant scenery that encroaches** on the playable zone or crushes the frame.
* **No exotic vegetation in bulk** outside the biome; count the species.
* **No sparse off-map area**: compare the density of the background to the measured reference.

### 4.E Process
* **No hand placement** of a piece that a scripted pass should place.
* **No "delivered" on the strength of a script that runs** or a green audit: screenshots judged + review + play.
* **No ballpark figure** ("~600 plants"): a number without a count is not one.
* **Never overwrite the human's touch-ups.**

---

## 5. Vocabulary (the names to know)

A vocabulary, not a library. Use it to speak precisely and to choose.

- **Shape**: footprint, envelope, organic outline, lobe, cove, bottleneck, isthmus, basin, knoll, ridge, terrace, spur, lip, embankment, gorge, chasm, shaft, ravine, natural bridge.
- **Level structure**: critical path, hub & spoke, loop-back, gating, lock & key, sectors, zoning, arena, choke point, pinch point, lane, "shooting gallery" (anti-pattern), closed pocket, connectivity.
- **Guidance**: weenie (distant landmark that draws the eye), breadcrumbing, vista, lead-in, backlighting, V-shape, threshold, arch, broken sight line, orientation landmark.
- **Combat**: static / mobile cover, cover cluster, engagement range, line of fire, flank, fallback point, spawn anchor, spawn exclusion, telegraph, advance warning.
- **Falls**: drop threshold, chevrons, rescue net, safe point, anti-escape floor.
- **Assembly**: greybox / blockout, set dressing, module, slot, grid, pivot, seam, end piece, insert, base / shaft / cap, run, variant, join, joint cover.
- **Rendering**: three-color ambience, key / fill / kicker, light pool, color budget, dominant, accent, semantic role, emission, bloom, clipping, luminance, fog matched to the sky, distance shells, silhouette, parallax.

---

## 6. New version of an existing level

Misclassifying the mode is the first source of a bad new version.

### 6.A Detect the mode (first action)
* **Touch-ups** — the human walked through and lists what bothers them. Fix those points, nothing else.
* **New version** — same place, same intent, substantive defects to address.
* **Overhaul** — new shape or new intent: this is a new level (fresh spec).

If ambiguous → one question: *"Do we fix these points, or rework the shape?"*

### 6.B Audit before touching
* Re-run the automatic audit and the fixed screenshots of the current version: this is the quantified starting point.
* List the defects of the previous version **verified** (image or measurement), then classify them: fixed, partial, still present, new.
* Re-read the canon since the last delivered version: the human's feedback is in it.

### 6.C What never changes silently
Without the human's explicit agreement, do not modify:
* the human's hand-made touch-ups (detected by fingerprint; the pass preserves and names them);
* entry points, spawn points, the objective and the safe points;
* names and IDs of objects referenced by code or save data;
* the order of lists that feed a seeded draw (append at the end only);
* the decided area and scale contract;
* the network status of an element (local scenery ↔ replicated gameplay).

### 6.D Correction levers, in order
Stop as soon as the feedback is handled:
1. **Construction** — floating pieces, holes, joins, free ends (blocking).
2. **Readability** — single focal point, visible objective, orientation, readable danger.
3. **Light and color** — color budget, light hierarchy, luminance.
4. **Composition** — clusters, breathing room, depth planes, off-map area.
5. **Shape** — outline, relief, routes: the most expensive, last, and only if the mode allows it.

---

## 7. Out of scope

This skill is not for: menus and HUD, numerical balancing of enemies, network code, pure cutscenes (a scripted sequence is not a level). If the brief is one of these, **say so** and apply this skill only to the spatial parts.

---

## 8. Pre-flight (before showing anything)

**Not optional.** Each box is ticked honestly or the level is not ready. What could not be verified is **announced** as such, never ticked.

- [ ] **Level reading** declared (§0.B), dials quantified and justified?
- [ ] **Project canon** and **extensions** (`.claude/level-design/`) reviewed; no `[USER]` entry violated? If the index cites a project checklist, has it been passed too?
- [ ] **Outline**: longest straight edge ≤ ~24 × the player's height, no geometric shape from above?
- [ ] **Ground**: continuous, no visible slabs, step at platform edges below the controller's step height?
- [ ] **Readable relief**: measured share of slopes > 10% matching `RELIEF`?
- [ ] **Flattening**: the share of flattened ground is measured and does not eat the plain?
- [ ] **Floating pieces = 0** (test on the lowest vertex of each piece)?
- [ ] **Shoreline gaps = 0** (rays all around each liquid/chasm)?
- [ ] **Safety net under every fall**: 100%?
- [ ] **Networks**: 0 free ends (pipes, cables, rails)?
- [ ] **Off-map area**: 0 peak in the playable envelope plus margin; the announced distant element is visible?
- [ ] **No enemy model** in the scenery?
- [ ] **Materials**: 0 materials from another biome, 0 materials rejected by the canon?
- [ ] **Single focal point** in each fixed screenshot?
- [ ] **Objective** identifiable from the entrance and from above?
- [ ] **Color budget**: hues counted ≤ 1 + 1 + 2, each accent has a single role?
- [ ] **Luminance** of each screenshot within target (default 60–160), clipped pixels < 5%?
- [ ] **Lights**: count ≤ budget, hierarchy ambience → guides → focal?
- [ ] **Clusters**: ≈ 90% of props grouped, no lone crate in a lane?
- [ ] **Circulation**: connectivity from the entrance ≥ 97%, 0 unreachable pocket, 0 forced pinch point below the minimum width?
- [ ] **Cover** within engagement range in every open combat zone?
- [ ] **Orientation**: each zone has a short name and a visible landmark?
- [ ] **Budget**: active renderers and lights under the project's ceilings?
- [ ] **Idempotence**: the pass, re-run, reports "nothing to do"?
- [ ] **Human touch-ups**: strictly identical before and after the pass?
- [ ] **Fixed screenshots** taken in a single scene state, from named cameras?
- [ ] **Independent review** (`level-design-reviewer`) done, and its blocking issues handled?
- [ ] **Played**: the player can stand on every surface, every fall has been tested?
- [ ] **Honest delivery** ready: measured, remaining, unverified?

If a box cannot be ticked honestly, the level is not ready. Fix before showing, or announce it.

---

## Guardrails

- The project's `[USER]` canon always overrides this skill. Conflict → reported, never settled alone.
- A value from this skill that the project has not confirmed remains a starting default: do not engrave it in the canon as a requirement from the human.
- Each new lesson (a defect encountered, a refusal by the human) is captured in the project canon with its provenance, via the `canon-tracker` skill if it is installed.
- This skill names no engine or asset pack: their pitfalls live in the project canon and in `level-design-build/references/pitfalls.md`, in generic form.
