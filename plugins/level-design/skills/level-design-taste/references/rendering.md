# Rendering: light, fog, color, density, depth

**Starting** values, measured on six reference scenes from a stylized low-poly asset pack,
then compared with the human's feedback. The project's canon replaces them as soon as it
sets others. A realistic style (PBR, computed GI) shifts the numbers, not the principles.

## Light

- **Ambient light is the main source.** A three-color ambient (sky / equator / ground) acts
  as GI: desaturated warm sky, clear blue equator, nearly black tinted ground. Test: a
  shaded area turns midnight blue **without** any fill light.
- **Anti-pattern #1: replacing the ambient light with lamps.** Measured reference: 84 lights
  in one scene; the AI version had placed 1,025 on the same area.
- **Hierarchy**: ambient → a few guide lights → **one** focal light. The focal light is the
  only tinted light casting a soft shadow, ≈ 2 × the intensity of the guide lights.
- **Shadows** on ≤ 20% of lights.
- **An emissive surface lights nothing** in real time: never count on it to light an area.
  Light fixtures are emissive meshes, not lights.
- Lights live under a dedicated root that can be disabled in one click.
- Interior and exterior details: [interior.md](interior.md), [exterior.md](exterior.md).

## Emissive, bloom, grading

- Without tonemapping, any emissive above 1.0 saturates to white: **LDR cap at 1.0**.
- **Neon comes from bloom**, not from lights: threshold 0.5–0.7, intensity 1.0–1.5;
  threshold ~0.85 when luminance must stay under control (snow, liquid, acid).
- **Emissive intensity is a narrative lever**:
  - ×1 everywhere = clean setup;
  - ×2 on 2–3 families = active equipment;
  - ×6 on **one** family = THE hotspot;
  - ×2–6 everywhere = deliberate clutter (rarely wanted).
- Screens and holograms: transparent surfaces (alpha 0.03–0.5), non-emissive; bloom does the
  rest. Glass never glows.
- A fine effect (laser, line) gets its glow from its **shape** (halo around a core), never
  from a luminosity that saturates.
- **Post-process: 4 to 6 settings, always the same** — bloom; contrast +8…+15; saturation
  +5…+12; shadows lowered and warm, midtones lifted and cool; vignette 0.4–0.5. No depth of
  field, grain, chromatic aberration or motion blur by default.
- **Measurements on screenshots**: average luminance 60–160 / 255; pixels > 250 < 5% (0%
  outside the intended emissives). Light is tuned **from the measurement**, not by eye.
- Reflective surface (smooth ground, liquid): plan for the key light's reflection. A "white
  streak" on the ground is often a specular highlight from a grazing key on ground that is
  too smooth.

## Fog and sky

- **Fog matched to the sky**: color ≈ 0.7 × the color of the bottom of the sky, otherwise
  the horizon shows a seam.
- Outdoors: linear fog, end = distance of the last readable plane (set by the map size).
  Nothing important beyond 0.7 × the fog end.
- Interior: black exponential fog, low density, measured on the project's reference.
- Celestial bodies ignore fog: they are the only sharp thing in the distance, which creates
  depth. Place them well beyond the last set-dressing plane (measured on the reference) to
  counter parallax; 10–15° apparent diameter; never tangent to a set-dressing edge.
- Ground mist = additive particles, not fog.
- **A spectacular sky kills silhouettes**: the sky serves the foreground.

## Color

- **Budget: 1 near-monochrome dominant + 1 complementary + 2 accents at most.** Count: 6
  hues in one scene = an observed defect.
- **One accent = one role.** Example palette: cyan = interactive / what opens; red = danger
  / enemy / perimeter; amber = structural flat fill, never luminous. A void edge is not
  marked with the "interactive" color.
- **One saturated focal per field of view**, plus a tiny counter-accent. In a cold scene,
  one warm note, and a large one (or the reverse).
- Chromatic variety comes from **albedo**, not from lighting.
- Large colored areas far away or up high; **the circulation plane stays calm**.
- A danger signal in the ground's hue does not read: change the hue or the shape.
- A saturated dark (violet, midnight blue) placed in a blue shadow reflects nothing and
  makes the view unreadable: lighten it. Check readability **in shadow** (zone luminance
  ≥ ~30).
- All the rock of a biome = **one** material family approved by the human.
- Material budget: 23–46 per scene; one atlas page carries most of the objects. The relief
  lives in the mesh's bevel, not in the normal map.

## Density and clusters

- Interior: props per grid cell, measured on the reference. Vertical distribution (× player
  height): 60% under 0.25, 25% between 0.25 and 0.65, 7% between 0.65 and 1.3, 9% above
  (pipes, light fixtures).
- ≈ 89% of props in clusters; ≤ 11% with no neighbor within ≈ 1.2 × player height. Nearest
  neighbor: median ≈ 1.2 × player height.
- **Cluster radius per role** (× player height): thematic 2–4 (3–5 objects that convey one
  function); generic 15–22; parallax: off-map scale.
- Typical vegetation cluster (radius ≈ 2 × player height, 4 species): 1 large + 2–3 medium +
  4–8 ground cover, at the foot of a rock.
- Distance to wall: median ≈ 1.2 × player height, 35% within one height. Clusters backed
  against walls, center clear except for THE focal point.
- Outdoors: **bare ground fills ≈ 55% of the frame**. It is the breathing room.
- **Density gradient aligned with the fog** (relative to the foreground, reference): 100%;
  ≈ 11%; ≈ 7%; ≈ 2%; ≈ 0.25% at the last readable plane; then only large masses.
  Band boundaries and absolute density measured on the project's reference.
- Repetition: ≈ 10 families repeated 20–140 times make up the "ground"; a notable building
  in **one** copy; 8–12 detail variants placed 1–5 times each.
- Rich presets (17–44 objects) built 2–3 times, then duplicated along an axis.

## Depth planes (to combine)

- **3 distance shells**, object count ≈ 5:2:1.
- **4 contrast tiers** (share of the fog end): sharp 0–8%, medium 8–30%, gray 30–60%, ghost
  60–100%.
- **Value tiers**, three bands that do not cross:
  - daytime: dark bottom / contrasted middle / light top;
  - night or interior: lightest bottom / readable middle / top in silhouettes (guides the
    eye toward the playable area).
- The same giant prop repeated at 3–7 distances along the view axis (the fog hides the
  repetition); one exception at scale 1, with its accessories, becomes the point of
  interest.
- **Occlusion**: a mid-ground plane in front of the light source. **Framing**: an object
  partly out of frame in the foreground.
- **Backlighting**: the strongest composition; it only costs a camera placement.
- **V shape**: two masses converge on a distant landmark; the fog fills the V.
- Quick skyline: the same element enlarged ×2.5, placed 20–60 × player height beyond the
  limit and 12–20 × in height.
- **Break up sight lines**: a threshold or arch every 2–3 modules; a long view remains
  allowed if it passes through 2–3 thresholds and drowns in the fog.

## Scale

- Silhouette ratio (large landscape) ≈ 1:20:100:250.
- An iconic prop enlarged ×10 in the distance gives the world its scale; medium objects on
  the ridges give the scale of the hills.
- **A single** vertical object sums up a district; restraint (few bright details) makes
  height believable.
- A spectacular event can come from a single detail enlarged (×9) rather than from a new
  model.
- FOV: 55–65 in-game; 38 telephoto; 25–30 poster; 84 monumental. Judge at the in-game FOV.
