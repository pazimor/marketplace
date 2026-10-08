# Reference recipes: measure instead of imitating

A reference scene (asset pack demo, already validated level) must be **measured** at the source. An eyeball analysis gets it wrong: on a real project, some "clouds" were disabled, "28 slabs" were a single squashed plate, and a "17" was actually 14.

## How

1. Read the scene **in its source file**: parse the hierarchy, resolve asset identifiers to paths, and compose local poses into world poses.
2. Rebuild outside the engine if needed (3D tool in script mode) to measure the meshes.
3. Cast rays over a grid (step set by the kit, e.g. half a module): height map "ground only" and "everything".
4. Count by script; deliver a "reproduce the measurements" section with the commands.
5. Explicit frame of reference: origin, azimuth, distance from a center; dimensions at the scale as placed.

## What to measure

- **Inventory** per family (counts).
- **Relief** per distance ring: heights p5/p50/p95, slope p50/p90, % > 10° and > 35°, dominant piece.
- **Transformations** per family: scales min/median/max, height/width ratio, tilt, sink depth (pivot − ground), share mirrored, yaw.
- **Placement**: nearest neighbor (p25/median/p75/p90); clusters (threshold ≈ 2 × the nearest-neighbor median: isolated, pairs, size, radius, number of species); "what borders what"; scale tiers.
- **Densities** per distance band and per category, in objects per grid cell of the kit.
- **Materials** per instance: overrides, colors, tilt slope, emissive intensities.
- **Rendering**: global settings, active lights, fog, post-process, sky, far clip.
- **Pitfalls** of the reference: a default material from another biome, a stray painted texture, emissive above the ceiling, objects beyond the far clip, objects without a collider, levitating elements that an audit would count as floating.
- For a network (pipes, cables): the connection **ports** measured on the mesh.

Each recipe ends with a checklist **"recipe → consequence for our level"**.

## What is NOT a recipe

- **The colors** of the reference: they are validated with the human. Priority order: the human's canon > the project's rendering bible > recipes per biome.
- **Its production defects**: no static flags, no LOD, colliders everywhere, lights with absurd intensity, oversized particle emitters, shadows cut off by too short a distance, duplicate skies.
- **Its scale**: a demo is a showcase (base and decorative track oversized compared to the player gauge). The game puts the figure back at the heart of the playable space.
- **An impression** ("~600 plants", "landmarks at regular intervals"): without a verified count, it is not a number.
- A setting that contradicts a game constraint (zero light against a mandated luminance, HDR emissive against an LDR ceiling).
