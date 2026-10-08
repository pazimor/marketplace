# Pitfalls learned the hard way (generic)

Each line comes from a defect actually encountered on a 3D game project, reworded without engine or pack names. Pitfalls specific to **your** engine and **your** assets go into the canon and the project's pitfalls file, not here.

## Driving the engine with an agent

- **Mutating then rendering in the same call returns the previous state.** Mutation and capture (or read) = two calls, always.
- A blocking native dialog ("save modified scenes?") freezes the agent: a pass must never open one; save or decline explicitly beforehand.
- Stale compiled code in the editor: an "impossible" behavior often comes from a library that was not reloaded. Check the binary's timestamp or the presence of a new field before concluding.
- A stale scene in memory mistaken for a regression: reopen it from disk before judging — but first check that it does not carry unsaved edits from the human.
- Long play sessions = spontaneous reloads and ghost states: keep them short.
- Never re-run a history entry from a code-execution tool: an old command restarted a network server outside the game.
- A temporary camera with the default far clip hides the distance: capture with the player camera's settings, from named cameras.
- A material cloned in memory may not render like the asset: test on a real asset.
- Teleporting a player places its root, not its feet: aim the root at surface height + foot height + a margin, otherwise you pass through thin surfaces and suspect a collider bug.

## Geometry and construction

- The bounds of a rotated plane mislead about its size (a lake looks ≈ 35% larger than it is).
- Footprints are read from the real colliders or bounds, never from pivots.
- An out-of-engine harness that routes on catalog boxes can be off by up to ~2 player heights on detailed facades: measure the real colliders.
- Forcing a rigid piece onto a mound makes it dive by the height of the mound: level a base under its footprint, place it, then stretch it upward if needed.
- A ground mesh of large triangles straddling a lake's lip interpolates the slope: the liquid rises. Cut the ground along the lip and the waterline.
- Add the relief **after** the plateaus, otherwise the fades erase it; keep the exact height under every placed marker.
- A human retouch inside a stamped group = the group is no longer regenerated; new set dressing goes into a new group, outside the bounding boxes of its pieces.
- When a pass rebuilds a group, re-validate the neighboring markers that did not move.
- A module with a hollow collider creates a closed pocket you get stuck in: use a solid collider.
- Prototyping geometry outside the engine (pure code + 3D tool) settles footprint conflicts before the first playable pass — then verify parity in the engine: the import found 39 defects that were invisible outside the engine.
- Check rotation 0 / scale 1 on a test cube from the start: an axis conversion left on a node cost two full iterations.
- Cut a kit along the **drawing** (bands and trim lines aligned across families), not along the thickest section. A piece ships closed (watertight) or not at all.

## Materials and rendering

- A projected (triplanar) material reads the atlas through the mesh's UVs: on a primitive, it shows the whole atlas; on a generated vertical face, a stray tile (pink). Use a dedicated gradient material for the walls.
- Asset families often ship with the ground material of a **different** biome by default: override it on each instance and audit.
- "Dark blotches with no object" on the ground are often a pattern painted by the shader, not shadows: diagnose the cause before fixing.
- An unexplained brown tint came from a warm fill light; a white streak, from the specular of a grazing key light on a too-smooth floor.
- Particles and objects created at runtime only exist in play: capture in play, or place an editor preview that is disabled on entering play.
- Light pit floors and a dark track read as crevasses; decorative floating rocks hide the focal point; a celestial body above the objective steals the gaze.

## Audit

- Testing a single vertex of a piece for "floating" gives false positives: the lowest vertex is the one to check.
- A pinch point is a defect only if you have to pass through it.
- Before correcting an audit that contradicts the prototype, replay it on the scene's colliders: in an hour, you can separate the real defects from the false positives.
- A waterline computed outside the engine is re-measured inside it, using the same definition as the audit.
- An anti-escape floor in a single plane does not follow the terrain: declare it per layout.
