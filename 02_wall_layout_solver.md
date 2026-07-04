# Process 2 — Wall Layout Solver

## Purpose
Given a wall face size, joint (grout) spacing rules, and a set of stones, design a
placement of stones across the wall that looks like a rustic random stone wall
(NOT a regular brick grid) and produces a visual map plus a placement list telling
the builder which stone goes where.

Build first with **dummy random stone data** matching the real stone profile, so
the aesthetic and packing can be judged before Process 1 exists. Later, swap the
dummy source for the real `catalogue.db` from Process 1.

## Stone profile (for the dummy generator)
- Rectangular faces, sizes 10–40 cm per side.
- Distribution centred near 13 x 30 cm; most stones long-and-narrow.
- Generator must be seedable (reproducible runs) and produce a configurable count
  and a configurable size distribution.
- Each dummy stone gets an ID (`D0001`…) and width_cm / height_cm, mirroring the
  real DB schema so the solver code doesn't care which source it reads.

## Inputs
- Wall dimensions in cm (default 1200 wide x 270 high).
- Joint spacing: `min_joint_cm` and `max_joint_cm` (the mortar gap allowed
  between stones, both horizontally and vertically).
- Stone set: from dummy generator now, from `catalogue.db` later.
- Random seed.
- Aesthetic constraints (see below), all configurable.

## Aesthetic / structural constraints
This is the heart of the tool. A pleasing random rubble/ashlar-ish wall wants:
- **Broken vertical joints.** No vertical seam should continue across more than
  ~2 stacked joints. Enforce a minimum horizontal offset between a joint in one
  course and the nearest joint in the course above/below (a "no running joints"
  rule, like bricklaying's stagger but irregular).
- **Varied course heights.** Rows are not uniform height; stones of differing
  heights sit within a loosely-defined course band, so the coursing looks
  natural, not ruler-straight.
- **No long horizontal seams either** if possible — occasional stones bridging
  two course bands ("through stones") add to the random look. This can be a
  stretch goal; a purely coursed layout is acceptable for v1.
- **Joint widths within [min, max].** The solver distributes slack as joint width
  rather than forcing perfect stone-to-stone contact.
- Avoid four stones meeting at a single point (a "+" cross joint) — a known weak,
  ugly pattern in stonework.

## Suggested approach (implementer's discretion)
Full optimal 2D packing is NP-hard; a heuristic is expected and fine.
A reasonable v1:
1. Work in loose horizontal **courses** of a target band height (e.g. pick a
   height from the available stones per course).
2. Fill each course left-to-right by selecting stones whose height fits the band,
   inserting joint gaps within [min,max] to consume slack.
3. When placing each stone, check the stagger rule against the course below and
   reject/greedily reselect if it would create a running joint or a cross joint.
4. Trim the last stone of a course or adjust joints to hit the wall's right edge
   cleanly (or flag a gap for a hand-cut stone — cutting is tolerated as a last
   resort).
5. Repeat course by course up to wall height.
Keep the selection strategy pluggable so it can be tuned later. Record any gaps
the solver couldn't fill and report them.

## Outputs
- **Visual map** — a rendered image (SVG preferred, PNG fallback) of the wall face
  drawn to scale: each stone as a rectangle, joints shown, each stone labelled
  with its ID. Colour or shade stones lightly so the layout reads clearly.
- **Placement list** — CSV / table: stone ID, x, y (bottom-left corner in cm on
  the wall), width, height, course number, storage_location (carried through from
  the DB when using real data so the builder knows where to fetch each stone).
- **Build order** — the placement list ordered course-by-course, left-to-right,
  bottom-to-top: the sequence to physically lay them.
- **Report** — coverage %, stones used vs available, joint width stats, count of
  any unfilled gaps or stones needing a cut.

## Architecture note
Separate the code into:
- `stones` source module (dummy generator now; `catalogue.db` reader later) behind
  a common interface so the solver is source-agnostic.
- `solver` module (the packing + aesthetic logic).
- `render` module (SVG/PNG map).
- `report` module (CSV + stats).
This keeps Process 2 cleanly swappable onto Process 1's real output.

## Tech
- Python 3. Rendering via `svgwrite` or hand-written SVG (preferred, crisp + scalable),
  or matplotlib for a quick PNG. Standard library elsewhere.

## Acceptance criteria
- Produces a full 1200x270 cm wall layout from dummy data with no overlaps and all
  joints within [min,max].
- Stagger rule visibly holds: no running vertical joints beyond the set limit.
- Visual map is legible and to scale with readable IDs.
- Placement list + build order exported.
- Swapping the stone source from dummy to a DB with the same schema requires no
  change to the solver/render code.

## Open questions to confirm before build
- Preferred output format for the map (SVG vs PNG).
- Whether v1 should be strictly coursed or attempt through-stones from the start.
- How aggressively to allow cuts vs leave gaps.
