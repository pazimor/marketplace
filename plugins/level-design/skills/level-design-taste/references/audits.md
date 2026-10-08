# Automatic audits: what to measure, against which target

Each build pass exposes a **read-only audit** that prints these measurements.
Default targets; the level spec or the project canon adjusts them. Each line comes
from a defect actually encountered.

**Golden rule: never show a level on the strength of an audit alone.** Green audit +
screenshots assessed + independent review + playtesting. And announce what could not
be verified.

## Shape and ground
| Check | Target | Why |
|---|---|---|
| Envelope area | decided area ± 3% | the human sets an area, not a shape |
| Longest straight edge of the outline | ≤ ~24 × player height | arena judged "too square" |
| Continuous ground | 0 visible slab; plateaus cut into the ground mesh | "everything rests on slabs" |
| Flattened ground share | listed; must not eat into the plain | 54 plateaus flattened 85% |
| Walkable slope | ≥ 99% of the playable ground under the max slope; max slope listed | — |
| Readable relief | slopes > 10° ≥ ~15% outside required flat zones | uniform ground, invisible relief |
| Step at plateau edges | under the controller's step height | a step that feels barely higher |

## Holes, edges, falls
| Check | Target | Why |
|---|---|---|
| Shoreline holes (rays cast all around each liquid or chasm) | 0 | notches, shoreline holes |
| Ground set-back behind the drawn shoreline | ≤ 0.8 × player height | — |
| Gap between shoreline piece and waterline | average ≤ 0.2 × player height | scalloping |
| Exposed corners of liquid planes | 0 | — |
| Safety net under EVERY fall | 100% | — |
| Safety net height | below the lowest walkable surface above it | false alarm under a walkway |
| Anti-escape floor | **declared** per layout, not inferred | 21 false positives out of 27 |
| Safe points | ≥ 2 × player height from any break; capsule clear; re-validated after any pass that rebuilds a neighboring group | safe point left under a new rock |

## Set dressing
| Check | Target | Why |
|---|---|---|
| Floating pieces | 0, tested on the **lowest vertex** of each piece | one vertex tested = false positives and false negatives |
| Buried pieces | sink depth matches the intended height | mountains buried 1 to 3 player heights deep |
| Networks (pipes, cables, rails) | 0 loose ends in the void; joints at the mesh's measured ports | 12 loose ends |
| Forbidden materials (other biome, rejected by the canon) | 0 | a material from another biome by default |
| Projected (triplanar) material on a primitive or vertical face | 0 stray atlas cells | whole atlas shown, pink wall |
| Hollow colliders (modules, buildings) | enclosed chambers filled in | pocket where the player gets stuck |
| Readability in shadow | zone luminance ≥ ~30 | dark rims unreadable |
| Off-map inside the playable envelope + 2 × player height | 0 vertices | distant set dressing placed at the heart of the map |
| Enemy body mesh in the set dressing | 0 | set-dressing drone = enemy drone |
| Announced distant set dressing visible | visible from the play area | base hidden behind a ledge |
| Particles casting a shadow | 0 | — |
| Human touch-ups | placements strictly identical before/after each pass | hand-moved objects overwritten |

## Circulation and combat
| Check | Target | Why |
|---|---|---|
| Main corridors | ≥ 6 player diameters (aim for 8–15 for 2–6 players) | street blocked at one diameter |
| Mandatory pinch points (no detour ≤ 2 s of sprint) | 0 under 3.5 player diameters | 47 reported, mostly nooks |
| Nooks, hollows in massifs, doors | listed as information, not as defects | false positives |
| Within a cluster of pieces | touch (≤ 0.6 diameter) or separate (≥ 3.5 diameters), never in between | one-diameter slits |
| Connectivity from the entrance | ≥ 97% of free ground | — |
| Pockets unreachable from open ground | 0 | 2 pockets |
| Obstruction of sight-blocking zones | spec target (e.g. ≥ 50% at 16 × player height) | dropped to 29% |
| Cover on open combat zones | present within engagement range | empty esplanade |
| Holes/hazards near the objective, the entrance, the bottlenecks | 0 | — |

## Budget
| Check | Target |
|---|---|
| Active renderers | below the project's cap; merge repetitive set dressing rather than raising the cap |
| Active lights | below the project's cap (interior: ≤ 1 per grid cell) |
| Set dressing instantiated at runtime | 0 unless explicitly decided |

## Screenshots
| Check | Target |
|---|---|
| Average luminance per screenshot | 60–160 / 255 |
| Pixels > 250 | < 5% (liquid, snow and emissive views) |
| Sealing (interior, magenta background) | 0 magenta pixels from every control point |

## Audit pitfalls
- **The audit lies if it is computed elsewhere.** An off-engine harness (catalog boxes,
  renderer bounds) is not the real colliders: hollow buildings, real walls set back by up
  to ~2 player heights. Report the figures measured by the audit run **inside the engine**;
  to tell a real defect from a false positive, replay on the scene's colliders.
- A non-convex collider is hollow: a sphere placed inside it does not touch it. Test with
  a ray that crosses the wall.
- The bounds of a rotated plane mislead about its real size; those of a merged object
  (renderers disabled) are empty: measure from the meshes.
- Count an alert from the start of the session only, not over the whole history.
- Measure the existing state **before** setting a target; if two of the human's rules
  diverge (a factor-of-3 gap observed), ask.
