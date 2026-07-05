"""Seeded spiral-accretion packer.

Drops a few random seed stones on the wall, then grows each cluster by
spiralling outward: at each step it casts a ray from the seed centre to the
current cluster boundary and butts a new stone against it. It always places the
largest available stone that fits the free space there, so open spots take big
random stones while tight pockets only admit the one small stone that fits (the
"look up a stone for the gap" behaviour). It stops when no stone can be placed
anywhere without cutting.

Geometry runs on a fine occupancy grid (cell ~3mm) so "does it fit" and pocket
size are simple array checks. 90-degree rotations keep every stone axis-aligned.
"""

import math
import random
from collections import deque

import numpy as np

from app.solver.geometry import region_intervals_at


def _orientations(stone):
    w = stone["width_cm"]
    h = stone["height_cm"]
    yield w, h, 0.0
    if abs(w - h) > 0.1:
        yield h, w, 90.0


def solve_spiral(walls, negs, stones, params):
    rng = random.Random(params.get("seed", 0))
    cell = params.get("cell_cm", 0.5)
    n_seeds = int(params.get("seeds", 4))

    if not walls or not stones:
        return [], _empty_report(len(stones)), []

    pts = [p for w in walls for p in w]
    min_x = min(p[0] for p in pts)
    max_x = max(p[0] for p in pts)
    min_y = min(p[1] for p in pts)
    max_y = max(p[1] for p in pts)

    cols = max(1, int(math.ceil((max_x - min_x) / cell)))
    rows = max(1, int(math.ceil((max_y - min_y) / cell)))

    inside = np.zeros((rows, cols), dtype=bool)
    for r in range(rows):
        y = min_y + (r + 0.5) * cell
        for x0, x1 in region_intervals_at(y, walls, negs):
            c0 = max(0, int(math.floor((x0 - min_x) / cell)))
            c1 = min(cols, int(math.ceil((x1 - min_x) / cell)))
            if c1 > c0:
                inside[r, c0:c1] = True

    occ = np.zeros((rows, cols), dtype=np.int32)
    used: set = set()
    placements: list[dict] = []

    # Precompute orientations (with cell dims) and a size-sorted order so we can
    # try largest-fit first and break early.
    ori = []
    for s in stones:
        lst = []
        for w, h, rot in _orientations(s):
            lst.append((w, h, rot, int(math.ceil(w / cell)), int(math.ceil(h / cell))))
        ori.append(lst)
    order = sorted(range(len(stones)), key=lambda i: -stones[i]["width_cm"] * stones[i]["height_cm"])

    def fits(r0, r1, c0, c1):
        if r0 < 0 or c0 < 0 or r1 > rows or c1 > cols:
            return False
        if not inside[r0:r1, c0:c1].all():
            return False
        # Footprint must be free. Stones sit flush (grout 0-3mm is a hairline);
        # a separation border would forbid ever attaching to the cluster.
        return bool((occ[r0:r1, c0:c1] == 0).all())

    def place(idx, r0, r1, c0, c1, w, h, rot):
        occ[r0:r1, c0:c1] = idx + 1
        used.add(idx)
        x = min_x + c0 * cell
        y = min_y + r0 * cell
        course = int((max_y - (y + h)) / 12)
        placements.append(
            {
                "stone_id": stones[idx]["id"],
                "code": stones[idx]["code"],
                "x_cm": round(x, 2),
                "y_cm": round(y, 2),
                "w_cm": round(w, 2),
                "h_cm": round(h, 2),
                "rotation_deg": rot,
                "course_index": course,
                "cut": None,
            }
        )

    def adj_occupied(r, c):
        return (
            (r > 0 and occ[r - 1, c] > 0)
            or (r + 1 < rows and occ[r + 1, c] > 0)
            or (c > 0 and occ[r, c - 1] > 0)
            or (c + 1 < cols and occ[r, c + 1] > 0)
        )

    def anchored_cells(ar, ac, sr, sc, w, h):
        wc = int(math.ceil(w / cell))
        hc = int(math.ceil(h / cell))
        c0 = ac if sc > 0 else ac + 1 - wc
        r0 = ar if sr > 0 else ar + 1 - hc
        return r0, r0 + hc, c0, c0 + wc

    def place_best(r, c):
        free_r = c + 1 < cols and inside[r, c + 1] and occ[r, c + 1] == 0
        free_l = c - 1 >= 0 and inside[r, c - 1] and occ[r, c - 1] == 0
        free_d = r + 1 < rows and inside[r + 1, c] and occ[r + 1, c] == 0
        free_u = r - 1 >= 0 and inside[r - 1, c] and occ[r - 1, c] == 0
        sc = 1 if free_r else (-1 if free_l else 1)
        sr = 1 if free_d else (-1 if free_u else 1)
        found = []
        scanned = 0
        for i in order:
            if i in used:
                continue
            if scanned > 150:
                break
            scanned += 1
            for w, h, rot, wc, hc in ori[i]:
                c0 = c if sc > 0 else c + 1 - wc
                r0 = r if sr > 0 else r + 1 - hc
                if fits(r0, r0 + hc, c0, c0 + wc):
                    found.append((i, r0, r0 + hc, c0, c0 + wc, w, h, rot))
                    break
            if len(found) >= 6:
                break
        if not found:
            return None
        # Random pick among the largest few that fit: fills well but keeps variety.
        i, r0, r1, c0, c1, w, h, rot = rng.choice(found)
        place(i, r0, r1, c0, c1, w, h, rot)
        return r0, r1, c0, c1

    inq = np.zeros((rows, cols), dtype=bool)
    frontier: deque = deque()

    def enqueue(r, c):
        if 0 <= r < rows and 0 <= c < cols and inside[r, c] and occ[r, c] == 0 and not inq[r, c]:
            inq[r, c] = True
            frontier.append((r, c))

    def enqueue_border(r0, r1, c0, c1):
        for c in range(c0 - 1, c1 + 1):
            enqueue(r0 - 1, c)
            enqueue(r1, c)
        for r in range(r0 - 1, r1 + 1):
            enqueue(r, c0 - 1)
            enqueue(r, c1)

    # Seed stones at random valid points (multiple nucleation sites).
    seed_points: list[list[float]] = []
    tries = 0
    while len(seed_points) < n_seeds and tries < n_seeds * 80:
        tries += 1
        r = rng.randrange(rows)
        c = rng.randrange(cols)
        if not inside[r, c] or occ[r, c] != 0:
            continue
        avail = [i for i in range(len(stones)) if i not in used]
        if not avail:
            break
        idx = rng.choice(avail)
        w, h, rot = rng.choice(list(_orientations(stones[idx])))
        wc = int(math.ceil(w / cell))
        hc = int(math.ceil(h / cell))
        r0, c0 = r - hc // 2, c - wc // 2
        if fits(r0, r0 + hc, c0, c0 + wc):
            place(idx, r0, r0 + hc, c0, c0 + wc, w, h, rot)
            enqueue_border(r0, r0 + hc, c0, c0 + wc)
            cx = min_x + (c0 + wc / 2) * cell
            cy = min_y + (r0 + hc / 2) * cell
            seed_points.append([round(cx, 1), round(cy, 1)])

    # Grow outward: each frontier cell (free, touching packed stone) is tried
    # once (BFS from the seeds). A placed stone exposes new frontier cells. This
    # fills the wall organically and stops when nothing more fits.
    safety = 0
    max_iter = rows * cols
    while frontier and safety < max_iter:
        safety += 1
        r, c = frontier.popleft()
        inq[r, c] = False
        if occ[r, c] != 0 or not adj_occupied(r, c):
            continue
        blk = place_best(r, c)
        if blk is not None:
            enqueue_border(*blk)

    free_area = float((inside & (occ == 0)).sum()) * cell * cell
    return placements, _build_report(placements, stones, walls, negs, free_area), seed_points


def _empty_report(n_available=0):
    return {
        "coverage_pct": 0.0,
        "stones_used": 0,
        "stones_available": n_available,
        "courses": 0,
        "cut_count": 0,
        "cut_total_cm": 0.0,
        "gap_count": 0,
        "gap_total_cm": 0.0,
        "joint_min_cm": 0.0,
        "joint_max_cm": 0.0,
        "joint_mean_cm": 0.0,
    }


def _net_wall_area(walls, negs):
    from app.geometry import polygon_area_cm2

    wall = sum(polygon_area_cm2(w) for w in walls)
    neg = sum(polygon_area_cm2(n) for n in negs)
    return max(0.0, wall - neg)


def _build_report(placements, stones, walls, negs, free_area):
    placed_area = sum(p["w_cm"] * p["h_cm"] for p in placements)
    net = _net_wall_area(walls, negs)
    rows = len({p["course_index"] for p in placements})
    return {
        "coverage_pct": round(100.0 * placed_area / net, 1) if net > 0 else 0.0,
        "stones_used": len(placements),
        "stones_available": len(stones),
        "courses": rows,
        "cut_count": 0,
        "cut_total_cm": 0.0,
        "gap_count": 1 if free_area > 400 else 0,
        "gap_total_cm": round(free_area, 1),
        "joint_min_cm": 0.0,
        "joint_max_cm": 0.0,
        "joint_mean_cm": 0.0,
    }
