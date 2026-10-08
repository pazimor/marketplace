# Arena and exterior map

Companion to `SKILL.md`. Starting values taken from a 2–6 player co-op game (player gauge
measured: radius ≈ 0.2 × player height, sprint ≈ 5 player heights per second); recompute
them on your project's player gauge.

## Size and shape

- **The area is derived from the players**: for 6 players who run and jump, validated
  arenas take ≈ 26 s of sprinting to cross; an area ≈ 25 times smaller was judged too
  small. The human sets the area per map.
- **Organic outline required**: lobes, coves, bottlenecks. Longest straight edge ≤ ~24 ×
  player height.
- Typical zoning: open arena · 4 sectors · two opposing halves separated by a diagonal
  hazard · an oriented valley with a gorge across it and 2 passages. Propose **three
  layout concepts** before choosing one (skill `level-design-build`).

## Relief

- Noise base (swell ±1.4 × player height + undulations ±0.5 ×), then flatten what must be
  flattened.
- Impassable ridges and "mountains", 5–10 × player height, that **really block the view**
  from ground level (measured obstruction, e.g. ≥ 50% at 16 × player height in the zones
  planned for it).
- Bowl rim of +0.8 to +1.2 × player height at the edges: a playable zone set in a
  depression caps readability.
- Canyon, gorge: legible walls (no material that stretches on a vertical face), dark
  floors (a light floor reads as a crack of light).
- Never sink a rigid piece (heap, embankment) onto a mound: it sinks by the height of the
  mound. Flatten a base under its footprint first.

## Liquids, chasms, falls

- A lake is flat. The shoreline is a **chain** of overlapping pieces (≥ 20°), the ground
  raised to the lip and cut under the crest, the waterline re-measured on the result.
- Gap between shoreline piece and waterline: average ≤ 0.2 × player height. Corners of
  liquid planes hidden under the ground.
- Number of fall hazards per `RELIEF`: e.g. 3 fixed chasms + 2 in combat mode.
- The consequence of a fall is decided by the human. Pattern validated in co-op:
  **recovery without death** to the nearest safe point (otherwise the last ground touched),
  safety net ≈ 0.2 × player height below the edge, with no burning strip.
- Safe points at ≥ 2 × player height from any break, capsule clear.
- Sun reflection on a liquid: plan for glare (emission ≤ 1, bloom threshold ~0.85, clipped
  pixels controlled).

## Gameplay modularity

- Two groups of layouts in one scene (e.g. "defense" and "combat") rather than two scenes.
- **Slots** spread across the area (≈ 40–55 per validated arena), each with ≥ 3 modules
  (hole / blocked / covered) drawn by a replicated seed. Replayability without new geometry.
- Modules blended into the set dressing, appearing and disappearing with a fade, never a
  hard on/off.
- Exclusions: no hole near the objective, the entrance or the bottlenecks; spawn exclusion
  around the center and the entrance; no spawn within < 12 × player height of an event.
- Elevated firing positions are useful only within range of the objective (beyond ≈ 60 ×
  player height, they are useless).

## Objective and combat

- Object to protect: 5–7 × player height, specific to the biome, built into the set
  dressing but identifiable, the **only** color hotspot. About 7 player heights from the
  entrance.
- 2–3 clusters of cover guaranteed around the objective. A lane of ≈ 9 s of running with no
  cover is a shooting gallery.
- No enemy group assigned to a fixed spot; ranged shooters spawn far away.
- Observed enemy density: ≈ 20–27 on a validated arena; hard cap set by the project.
- Danger warning ≥ 4 s; a lobbed projectile shows its impact on the ground.

## Exterior rendering

- **Planet**: 0 lights, or exactly 1 directional light (elevation ≈ 40–50°, soft shadows).
  Nothing in between; no point light, even in a camp.
- **Space**: exactly 3 directional lights — warm key (≈ 2.0), underside kicker (planetary
  bounce, ≈ 2.25), cool fill (≈ 0.3) — flat midnight-blue ambient, no fog, near-black sky,
  60–75% of the frame in textured black.
- Ground: the light/dark contrast of the relief comes from the slope-driven shader, not
  from light. If a triplanar shader only switches to rock on steep slopes, the relief does
  not read: tune the switch on the generated ground.
- Low ground glossiness (smoothness ≈ 0.2–0.3): ground at 0.55 reads as ice.
- Two biomes = one material variant (3 colors + the switch slope), nothing more.

## Off-map

- **Density bands** beyond the limit (see the gradient in `rendering.md`), alive (ships,
  vehicles, cannons firing toward the horizon, drilling rigs, convoys) but local, not
  replicated.
- 0 vertices within the playable envelope + 2 × player height.
- Compare the background density against the measured reference: a sparse background is a
  frequent piece of feedback from the human.
- Distant set dressing meant to be visible (base, landmark) is checked **from the play
  area**.

## Minimum screenshots for an arena

Overhead shot (readable outline) · overhead shot of each landmark (lake, chasm) · entrance
(and elevated entrance) · objective (in-game if it only exists at runtime) · each zone ·
each shoreline or hazard edge · background / horizon. All at the project's reference
resolution, at the game's far clip.
