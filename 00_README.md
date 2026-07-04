# Sandstone Wall Builder — Project Overview

Two independent tools that share a common stone data schema.

## The problem
A quantity of sandstone blocks, near-rectangular with ~90° corners, faces 10–40 cm
per side (most ~13 x 30 cm), are to be built into a random rustic-look stone wall
2.7 m high x 12 m long (270 x 1200 cm). The wall face may be rustic/uneven in depth
so only the 2D face of each stone matters. Cutting stones is tolerated only as a
last resort.

## The two tools
1. **Stone Cataloguer** (`01_stone_cataloguer.md`)
   Overhead camera → detect, measure (in cm), ID, crop and store every stone into
   an SQLite database plus an image folder. No LiDAR needed; a plain overhead
   photo with ArUco scale markers is more accurate for flat measurement.

2. **Wall Layout Solver** (`02_wall_layout_solver.md`)
   Given wall size + joint spacing + a stone set, design a staggered, natural-
   looking placement and output a visual map, a placement list, and a build order.
   Built first against dummy random stone data, then pointed at the real database.

## Shared schema
Both tools speak the same stone record: `id`, `width_cm`, `height_cm`,
`storage_location` (+ the cataloguer adds capture/position metadata). The solver
reads stones behind an interface so the dummy generator and the real DB are
interchangeable.

## Suggested build order
Build the **Wall Layout Solver with dummy data first** — it needs no hardware and
lets the random-wall aesthetic be judged and tuned early. Then build the Cataloguer
and swap its real DB in as the solver's stone source.

## Not in scope
Live AR guidance was considered and dropped. These two tools are the whole project.
