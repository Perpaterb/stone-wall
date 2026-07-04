# Process 1 — Stone Cataloguer

## Purpose
Ingest overhead photos of sandstone blocks laid out on a flat sheet, detect each
stone, measure its 2D face in real-world centimetres, assign a stable ID, crop an
individual image of each stone, and write everything into a database plus an
image folder.

The stones are near-rectangular blocks with roughly 90-degree corners. Face sizes
range 10–40 cm per side, most around 13 x 30 cm. Only the 2D face matters; depth
(front-to-back) is ignored.

## Hardware / capture assumptions
- A single camera mounted directly above a flat sheet, shooting down.
- Stones laid on a contrasting background (dark sheet for pale sandstone) so
  edges threshold cleanly. Stones should NOT touch each other — leave a visible
  gap between every stone.
- Four **ArUco markers** placed at known real-world positions (one near each
  corner of the working area). These give two things:
    1. Scale (pixels → cm).
    2. Perspective correction (un-warp a slightly angled shot to true top-down).
- The physical distance between marker centres is a known, configurable constant
  (e.g. markers span 100.0 cm x 100.0 cm). This is the calibration.

## Inputs
- One or more overhead photos (a "batch" = one photo of up to ~30 stones).
- Per batch, a user-supplied **storage location** label (e.g. "Pallet B",
  "Row 3"). This is typed once per photo, not per stone.
- Config: ArUco dictionary, marker span in cm, expected stone size range (for
  sanity-filtering out noise / debris).

## Pipeline
1. **Detect ArUco markers.** Find all four. If fewer than four, warn and abort
   that batch (bad photo). Use marker corners to build a homography.
2. **Warp to top-down.** Apply the homography so the output image is a true flat
   view where 1 cm maps to a fixed pixel count. Record the px-per-cm scale.
3. **Segment stones.** Threshold stones against the background (Otsu or adaptive).
   Morphological open/close to clean noise. Find external contours.
4. **Filter contours.** Discard anything whose bounding size falls outside the
   plausible stone range (e.g. min side < 8 cm or max side > 45 cm), and discard
   the marker regions themselves.
5. **Measure each stone.** Fit a minimum-area rotated rectangle
   (`cv2.minAreaRect`) to each contour. Convert the two side lengths to cm using
   the scale. Report width = longer side, height = shorter side (or keep both raw
   plus an orientation angle).
6. **Assign IDs.** Stable, human-friendly, sequential across the whole catalogue
   (not per-batch). e.g. `S0001`, `S0002`… Persist a counter so re-runs don't
   collide.
7. **Crop each stone.** From the warped image, crop the (rotated) rectangle to a
   clean upright thumbnail. Save as `<ID>.png`.
8. **Record grid position.** Within the sheet, record each stone's centre X/Y in
   cm so it can be physically located on that sheet/pallet later.
9. **Write to DB.**

## Database schema (SQLite)
Table `stones`:
- `id`            TEXT PRIMARY KEY   -- e.g. "S0001"
- `width_cm`      REAL               -- longer face dimension
- `height_cm`     REAL               -- shorter face dimension
- `angle_deg`     REAL               -- rotation of fitted rect (diagnostic)
- `storage_location` TEXT            -- user label for the batch, e.g. "Pallet B"
- `sheet_x_cm`    REAL               -- centre position on the sheet
- `sheet_y_cm`    REAL
- `source_photo`  TEXT               -- filename of the batch photo
- `crop_path`     TEXT               -- path to the per-stone crop image
- `captured_at`   TEXT               -- ISO timestamp

## Outputs
- `catalogue.db` — the SQLite database above.
- `crops/` — folder of per-stone thumbnail images named by ID.
- `debug/` — per-batch annotated overlay image (detected rects + IDs drawn on the
  warped photo) so the operator can eyeball that detection was correct.
- A short console + CSV summary per batch: N stones found, size distribution,
  anything filtered out.

## Tech
- Python 3, OpenCV (`opencv-contrib-python` for ArUco), NumPy, SQLite3 (stdlib),
  optionally Pillow for clean crop saving.

## Operator workflow (how it's used)
1. Lay ~30 non-touching stones on the sheet inside the marker frame.
2. Type the storage location label for this batch.
3. Take / point at the photo → run the tool on it.
4. Check the `debug/` overlay: every stone boxed, no debris boxed, sizes sane.
5. Physically move that batch to its labelled storage.
6. Repeat until all stones catalogued.

## Acceptance criteria
- Measured dimensions within ~2–3 mm of hand-measured ground truth on a test set.
- No stone missed, no non-stone falsely catalogued, on a clean test photo.
- Re-running does not duplicate or collide IDs.
- DB, crops, and debug overlays all produced.

## Open questions to confirm before build
- Exact ArUco dictionary and physical marker span you'll use.
- Camera resolution (drives achievable mm accuracy).
- Whether stones will ever touch (if unavoidable, need watershed separation —
  more complex; prefer to enforce gaps instead).
