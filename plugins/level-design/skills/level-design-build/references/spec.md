# Level spec template

Order taken from the last validated arena spec on a real project. Each section has a reason to exist; do not skip one without saying so. The figures in a spec are **first-creation** values, adjustable afterwards by the human.

```markdown
# <Type> <Name> — spec vN

Task: <roadmap ID> · Procedure: level-design-build · Based on: <closest validated spec>
Recipes: <recipes file> · Quality control: <project checklist> · Frame: <axes, origin>

## 0. Decisions from the sponsor
<empty when written; filled in verbatim after the questions. Nothing is built before then.>

## 1. Requirements
1. <requirement, with its source: a quote from the human or a canon ID>
2. …
<each will receive a verdict of achieved / partial / missed at delivery>

## 2. Defects not to reproduce
- <lesson from previous levels, with canon ID>
- <pitfall specific to the reference>
- <error from an earlier analysis, corrected>

## 3. Already verified automatically
| Candidate asset | Measured dimensions | Objects / colliders | Proposed role |
What is MISSING (measured): …
Technical constraints observed: …

## 4. Intent
<one paragraph: the story of the place.>
What we keep from the reference: … · What we rebuild at game scale: …

## 5. Three master-plan concepts
### Concept A — <name>
<ASCII sketch, legend shared by all three>
| Area | Box | Longest straight edge | Entry → objective (run time, s) |
| Zone | Footprint | Content | Relief |
Circulation · sightlines · hazards · strength · weakness
### Concept B — …
### Concept C — …
Recommendation: <which one, and why>

## 5bis. Detailed plan of the recommended concept
- Relief: function, amplitudes, plateaus, slope targets
- Main hazard and its readability
- Core of the level and objective
- Off-map: density bands
- Enemy arrivals, fallback points, safety floor
- **Orienting by voice**: a short name and a visible landmark per zone

## 6. Variants and modularity
Layout groups (modes) · slots and modules per zone · exclusions · number of slots derived from the area.

## 7. Living environment
| Option | Principle | Where | Cost | Gameplay | Risk |
Recommendation · list of living elements with their cadence

## 8. Objective, light, performance
Central object candidates (assembly, target size, readability) · rendering / sky / fog / color budget · **named capture cameras** (position, direction, FOV) ·
| Item | Estimated renderers | Ceiling |

## 9. Build pass
Files, commands, roots · reused building blocks · blocks to consolidate · integrated audits · quantified plan achieved and deviations accepted · versioned corrective passes.

## 10. Questions for the sponsor
1. <structuring question> — (a) … (b) … (c) … — **Rec: (x)**, because …
2. …

## 11. Definition of Done
- [ ] Spec validated (§0 filled)
- [ ] Idempotent build: 2nd run "nothing to do"
- [ ] Audit green, quantified
- [ ] Fixed-camera captures: luminance, clipping, readability per view
- [ ] Gameplay scripted: surfaces, falls, modes
- [ ] `level-design-reviewer` review with no blockers
- [ ] Honest delivery: measured / remaining / unverified
```

## Why this order

- **§0 empty at the start**: you do not build on an imagined decision.
- **§1 numbered**: delivery becomes auditable requirement by requirement.
- **§2** is the anti-regression memory; **§3** separates what is measured from what is assumed.
- **§5 three concepts**: forces a real choice rather than the first idea.
- **§5bis "by voice"**: in co-op, a level is played by talking to each other.
- **§10 last**, but passed on first: the questions follow from everything above them.
