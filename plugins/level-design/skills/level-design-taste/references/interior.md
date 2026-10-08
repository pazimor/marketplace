# Room, corridor, interior

Companion to `SKILL.md`. No distance is fixed here: heights, widths, spacings, ranges and
densities are derived from the **user's kit** (grid contract below) and from the user's
measured reference scene (`level-design-build`, recipes). Rules are expressed in modules,
cells and proportions.

## The box

- **Grid contract set before any piece**: horizontal module, wall slot, vertical module,
  floor height (top to top), thicknesses, alignment tolerance. Values **measured on the
  user's assets**, never invented.
- Standard corridor = 1 module; major gallery = 2 modules. Clear height = the height the kit
  gives under a floor. Mezzanines at +1 floor. A single main floor level per room.
- Conventional pivots (wall: bottom, start, on the line; floor: min corner, top of slab;
  ceiling: min corner, underside); naming `Family_Type_Variant_Length`; named anchors at
  the seams.

## Walls

- Only 4–5 variants (they carry 80% of the walls), ≈ 1 variant per 3 standard walls.
- A run is uniform; a variant enters as a **contiguous cluster** at a justified spot. Never
  a regular alternation. Switching wall family mid-room is a break in the visual language.
- Tall wall = plinth + n × shaft + cap. Never two full walls stacked (floating plinth at
  mid-height).
- A change in wall height = pillar at the joint. A corner pillar that "looks like an added
  piece" is a defect.
- ≈ 20% of elements off-grid allowed **once the box is placed** (infill, panels).

## Placement rules (reject in bulk, with a named message)

- Never a door in a corner, at the end of a wall, next to another door, at the edge of a
  void, or against a single wall.
- A window is never at a free end or in a corner; a facade window is paired with its
  interior half.
- Stairwell shaft = continuous full-height wall; floor opening ≥ 2 modules above a
  staircase, no ceiling above.
- Slab edge closed on the void side; end cap closed on any exposed end.
- Ceiling overhanging the tops of the walls, otherwise a grazing sight line gets through.
- Slight overlap between neighboring slabs (within the grid contract's tolerance), otherwise
  a hairline of daylight shows. A visible gap between two elements is always noticed.
- Floor setback inward, otherwise a slit under the ceiling.
- Only stretch the flat strips designed for it (faces on a flat texture fill); never a
  bevel, a detail or a pattern. **A piece defect is fixed at the source**, never by scaling
  in the placement pass.

## Interior lighting

- Three-color ambient, stronger than outdoors (≈ 1.7).
- Budget: ≤ 1 light per grid cell; maximum density is measured on the project's reference.
- Corridor: lights at the grid pitch, alternating left/right, warm white, no shadows, range
  just beyond the pitch.
- Room fill: ≈ 0.4 × the corridor's intensity, range wider than the corridor's.
- Focal: **one** tinted light, ≈ 2 × the corridor, widest range, the only one casting soft
  shadows. No spotlights, no directional lights indoors.
- Red alert accent and short-range screens.
- Light-ray volumes: 3 at most, at focal points only.
- **Three-tier lighting** without extra lights: bars on the ceiling or at the top of walls;
  emissive strips flush with the floor and along the skirting; bands integrated into the
  furniture. Strips **broken** (dashes of varied lengths), not one continuous line.

## Identity and set dressing

- **Room identity without geometry**: a wall band colored by function, matching lockers and
  pictograms, ceiling trims in a different hue.
- Signage above doors, in the upper band of the wall, low emission (bloom does the neon).
- Floor: a plate or ring painted at a regular interval of modules along the axis; chevrons
  along void edges;
  grating channels against the walls.
- Ceiling: piping along the corridor axis, otherwise it reads as an empty plane. A large
  technical gallery may have **no** ceiling at all: the black above gives the scale.
- **Sight lines**: an arch or threshold every 2–3 modules; a long view remains allowed if it
  passes through 2–3 thresholds and dissolves into the black fog.
- Props: density measured on the project's reference, ≈ 90% in clusters, backed against
  walls, center clear except for the focal point, ≈ 30% as free-form scatter. **The
  circulation corridor is off-limits to props by construction** (circulation polygon shrunk
  by a margin derived from the player gauge).
- Signs of life: litter, one recurring mark, screens never identical, **a single**
  off-axis mess on an orthogonal floor.
- Window to space: flat midnight-blue ambient, no fog, very large far clip; the void carries
  a non-zero dark texture.
- Scene hierarchy: root nodes per category (structure / props / signage / ceilings), each
  can be disabled; rooms as containers.

## Interior-specific checks

- **Sealing test**: background in an impossible color (magenta), rendered from the center,
  each opening, each door and each outside corner; count the magenta pixels → 0. It is the
  only objective verdict of "no hole".
- ≤ 1 light per grid cell.
- Fixed screenshots at the player's eye height.
- Severity scale: blocking (hole, open joint, wrong pivot or scale) > major (visible
  stretching, broken silhouette, glaring repetition, z-fighting) > minor (invisible from a
  game camera). A defect visible only from a viewpoint never seen in play is minor — except
  for what can be seen from outside.
