"""Rustic wall packing solver (v3, skyline).

Instead of laying uniform horizontal courses (which forces a brick-like rowed
look), this models the wall as a height profile ("skyline") over narrow columns
and repeatedly fills the current lowest notch with a varied stone, the way a real
waller works: look at the whole wall, drop a stone into the lowest gap, repeat.
The skyline becomes jagged, so stone heights vary side to side and bed joints do
not run, giving a random-rubble appearance rather than clean courses.

Coordinates are the plan's (y down). We work in height-above-bottom u = max_y - y,
so u = 0 at the wall bottom and grows upward. Packs by bounding box; true shapes
are rendered.
"""

import random

from app.solver.geometry import column_intervals

VERSION = "skyline-3"

_MIN_SIDE = 8.0
_EPS = 1e-6


def _orientations(stone):
    w = stone["width_cm"]
    h = stone["height_cm"]
    yield w, h, 0.0
    if abs(w - h) > 0.1:
        yield h, w, 90.0


def _pick(avail, max_w, max_h, rng):
    """Choose a stone orientation that fits [max_w] wide and [max_h] tall.

    Favours filling the ledge width, but keeps height variety (which is what
    breaks up rows), so we pick randomly among a widthwise-sorted shortlist.
    """
    cands = []
    for s in avail:
        for horiz, vert, rot in _orientations(s):
            if horiz <= max_w and _MIN_SIDE <= vert <= max_h and horiz >= _MIN_SIDE:
                cands.append((horiz, vert, rot, s))
    if not cands:
        return None
    cands.sort(key=lambda c: -c[0])
    shortlist = cands[: min(10, len(cands))]
    return rng.choice(shortlist)


def solve(walls, negs, stones, params):
    rng = random.Random(params.get("seed", 0))
    gmin = params.get("grout_min_cm", 1.0)
    gmax = params.get("grout_max_cm", 3.0)
    # Bias joints toward the minimum so the wall reads as packed stone, not mortar.
    vgrout = gmin + 0.25 * (gmax - gmin)
    dx = params.get("column_cm", 2.0)

    if not walls:
        return [], _empty_report()

    pts = [p for w in walls for p in w]
    min_x = min(p[0] for p in pts)
    max_x = max(p[0] for p in pts)
    min_y = min(p[1] for p in pts)
    max_y = max(p[1] for p in pts)

    ncols = max(1, int(round((max_x - min_x) / dx)))
    colx = [min_x + (c + 0.5) * dx for c in range(ncols)]
    ivals = [column_intervals(x, walls, negs, max_y) for x in colx]

    cur = [0] * ncols  # index into that column's interval list
    height = [0.0] * ncols  # current fill height u
    done = [False] * ncols
    for c in range(ncols):
        if ivals[c]:
            height[c] = ivals[c][0][0]
        else:
            done[c] = True

    pool = {s["id"]: s for s in stones}
    used: set = set()
    placements: list[dict] = []
    gaps: list[float] = []
    joint_widths: list[float] = []

    def available():
        return [s for sid, s in pool.items() if sid not in used]

    def ceiling(c):
        return ivals[c][cur[c]][1]

    def advance(c, to_u):
        height[c] = to_u
        if to_u >= ceiling(c) - _EPS:
            if cur[c] + 1 < len(ivals[c]):
                cur[c] += 1
                height[c] = ivals[c][cur[c]][0]
            else:
                done[c] = True

    safety = 0
    limit = ncols * 60 + 500
    while safety < limit:
        safety += 1
        # Lowest, leftmost open column.
        target = -1
        best = 1e18
        for c in range(ncols):
            if not done[c] and height[c] < best - _EPS:
                best = height[c]
                target = c
        if target < 0:
            break

        base_u = height[target]
        # Gather the flat run to the right at the same height (a level ledge).
        run_end = target
        while (
            run_end + 1 < ncols
            and not done[run_end + 1]
            and abs(height[run_end + 1] - base_u) < _EPS
        ):
            run_end += 1
        run_cols = run_end - target + 1
        run_w = run_cols * dx
        # Height room is the lowest ceiling across the run (so a wide stone never
        # pokes past a sloped top or into a hole).
        ceil_u = min(ceiling(c) for c in range(target, run_end + 1))
        avail_h = ceil_u - base_u

        pick = _pick(available(), run_w, avail_h, rng) if avail_h >= _MIN_SIDE else None
        if pick is None:
            # Cannot fill this notch: raise it to meet its lower neighbour (or the
            # ceiling). Only a sizeable unfilled area counts as a real gap; thin
            # slivers are just mortar.
            left_h = height[target - 1] if target > 0 and not done[target - 1] else ceil_u
            right_h = height[run_end + 1] if run_end + 1 < ncols and not done[run_end + 1] else ceil_u
            raise_to = min(ceil_u, min(left_h, right_h))
            if raise_to <= base_u + _EPS:
                raise_to = ceil_u
            area = (raise_to - base_u) * run_w
            if area > 80.0:
                gaps.append(area)
            for c in range(target, run_end + 1):
                advance(c, raise_to)
            continue

        w, h, rot, stone = pick
        span_cols = min(run_cols, max(1, int(round((w + _EPS) / dx + 0.4999))))
        x0 = min_x + target * dx
        y_top = max_y - (base_u + h)
        placements.append(
            _place(stone, x0, y_top, w, h, rot, int(base_u // 12), None)
        )
        used.add(stone["id"])
        joint_widths.append(round(vgrout, 2))
        new_u = base_u + h + vgrout
        for c in range(target, target + span_cols):
            advance(c, new_u)

    report = _build_report(placements, stones, walls, negs, [], gaps, joint_widths)
    return placements, report


def _place(s, x, y, w, h, rot, course, cut):
    return {
        "stone_id": s["id"],
        "code": s["code"],
        "x_cm": round(x, 2),
        "y_cm": round(y, 2),
        "w_cm": round(w, 2),
        "h_cm": round(h, 2),
        "rotation_deg": rot,
        "course_index": course,
        "cut": cut,
    }


def _empty_report():
    return {
        "coverage_pct": 0.0,
        "stones_used": 0,
        "stones_available": 0,
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


def _build_report(placements, stones, walls, negs, cuts, gaps, joints):
    placed_area = sum(p["w_cm"] * p["h_cm"] for p in placements)
    net = _net_wall_area(walls, negs)
    rows = len({p["course_index"] for p in placements})
    return {
        "coverage_pct": round(100.0 * placed_area / net, 1) if net > 0 else 0.0,
        "stones_used": len(placements),
        "stones_available": len(stones),
        "courses": rows,
        "cut_count": len(cuts),
        "cut_total_cm": round(sum(cuts), 1),
        "gap_count": len(gaps),
        "gap_total_cm": round(sum(gaps), 1),
        "joint_min_cm": round(min(joints), 2) if joints else 0.0,
        "joint_max_cm": round(max(joints), 2) if joints else 0.0,
        "joint_mean_cm": round(sum(joints) / len(joints), 2) if joints else 0.0,
    }
