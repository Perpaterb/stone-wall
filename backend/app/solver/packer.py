"""Rustic wall packing solver (v2).

Fills the wall region course by course from the bottom up. Each course:
  - picks a varied band height from the available stone heights,
  - selects stones (weighted-random for variety) to fill the course width,
  - distributes the leftover space as grout within [min, max] plus a random edge
    offset, so courses do not all left-align and the right edge is not always cut,
  - alternates fill direction per course,
  - occasionally stands a tall stone as a through-stone spanning two courses,
  - only cuts a stone where a sloped wall edge leaves a sliver too small to fill.

Packs by bounding box; true shapes are rendered. Coordinates are the plan's
(y increases downward), so the wall bottom is the largest y.
"""

import random

from app.solver.geometry import region_intervals_at, subtract_intervals

_MIN_STONE_CM = 8.0


def _orient(width_cm, height_cm, target, tol):
    """Orientation whose vertical side is within [target-tol, target+1]."""
    best = None
    for horiz, vert, rot in ((width_cm, height_cm, 0.0), (height_cm, width_cm, 90.0)):
        if target - tol <= vert <= target + 1.0:
            score = abs(target - vert)
            if best is None or score < best[0]:
                best = (score, horiz, vert, rot)
    return None if best is None else (best[1], best[2], best[3])


def _orient_through(width_cm, height_cm, target2, tol):
    for horiz, vert, rot in ((width_cm, height_cm, 0.0), (height_cm, width_cm, 90.0)):
        if target2 - tol <= vert <= target2 + tol:
            return horiz, vert, rot
    return None


def _choose_band_height(short_sides, rng):
    hs = sorted(short_sides)
    lo = hs[int(len(hs) * 0.2)]
    hi = hs[int(len(hs) * 0.8)]
    return max(_MIN_STONE_CM, rng.uniform(lo, hi))


def _weighted_pick(cands, rng, x_now, prev_joints, stagger):
    """Favour larger stones (fewer joints) but keep variety, and bias away from
    a joint that would run with the course below."""
    ordered = sorted(cands, key=lambda c: -c[1][0])
    top = ordered[: min(6, len(ordered))]
    good = [
        c
        for c in top
        if all(abs((x_now + c[1][0]) - pj) >= stagger for pj in prev_joints)
    ]
    return rng.choice(good if good else top)


def solve(walls, negs, stones, params):
    rng = random.Random(params.get("seed", 0))
    gmin = params.get("grout_min_cm", 1.0)
    gmax = params.get("grout_max_cm", 3.0)
    stagger = params.get("stagger_min_cm", 6.0)
    tol = params.get("band_tol_cm", 3.0)
    through_prob = params.get("through_stone_prob", 0.06)

    if not walls:
        return [], _empty_report()

    pts = [p for w in walls for p in w]
    min_y = min(p[1] for p in pts)
    max_y = max(p[1] for p in pts)

    pool = {s["id"]: s for s in stones}
    used: set = set()
    placements: list[dict] = []
    cuts: list[float] = []
    gaps: list[float] = []
    joint_widths: list[float] = []

    def available():
        return [s for sid, s in pool.items() if sid not in used]

    def fill(x_left, x_right, course_bottom, band, ci, this_joints, new_blocked):
        width = x_right - x_left
        if width < _MIN_STONE_CM:
            # Sliver at a sloped edge: cut one stone to fit, else record a gap.
            for s in available():
                ori = _orient(s["width_cm"], s["height_cm"], band, tol)
                if ori and ori[0] > width:
                    w, h, rot = ori
                    placements.append(
                        _place(s, x_left, course_bottom - h, width, h, rot, ci,
                               {"needed": True, "from": "right", "removed_cm": round(w - width, 1)})
                    )
                    used.add(s["id"])
                    cuts.append(w - width)
                    return
            gaps.append(width)
            return

        # Through-stone chance (needs a full further course above it).
        if (
            rng.random() < through_prob
            and course_bottom - 2 * band >= min_y
            and width > band
        ):
            for s in available():
                ori = _orient_through(s["width_cm"], s["height_cm"], 2 * band, tol)
                if ori and ori[0] <= width - gmin and course_bottom - ori[1] >= min_y - 0.5:
                    w, h, rot = ori
                    placements.append(_place(s, x_left, course_bottom - h, w, h, rot, ci, None))
                    used.add(s["id"])
                    new_blocked.append((x_left, x_left + w))
                    # Continue filling the rest of this course after the through-stone.
                    fill(x_left + w + gmin, x_right, course_bottom, band, ci, this_joints, new_blocked)
                    return

        # Greedily gather stones to fill the width (min grout between them).
        chosen: list = []
        span = 0.0
        guard = 0
        while guard < 200:
            guard += 1
            gaps_so_far = len(chosen) * gmin
            remaining = width - span - gaps_so_far
            if remaining < _MIN_STONE_CM:
                break
            cands = []
            for s in available():
                ori = _orient(s["width_cm"], s["height_cm"], band, tol)
                if ori and ori[0] <= remaining:
                    cands.append((s, ori))
            if not cands:
                break
            s, ori = _weighted_pick(cands, rng, x_left + span, this_joints, stagger)
            chosen.append((s, ori))
            used.add(s["id"])
            span += ori[0]

        if not chosen:
            gaps.append(width)
            return

        k = len(chosen)
        inner_gaps = k - 1
        slack = width - span

        if inner_gaps > 0:
            per = slack / inner_gaps
            gap_w = min(gmax, max(gmin, per))
        else:
            gap_w = 0.0
        used_width = span + inner_gaps * gap_w
        edge_slack = width - used_width

        # A large edge_slack means the pool ran short here: report the shortfall.
        if edge_slack > 2 * gmax:
            gaps.append(edge_slack)
            left_edge = gmin
        else:
            # Random split of the edge slack so courses do not all align.
            left_edge = edge_slack * rng.uniform(0.3, 0.7)

        order = chosen if ci % 2 == 0 else list(reversed(chosen))
        x = x_left + left_edge
        for idx, (s, (w, h, rot)) in enumerate(order):
            placements.append(_place(s, x, course_bottom - h, w, h, rot, ci, None))
            this_joints.append(round(x, 2))
            this_joints.append(round(x + w, 2))
            x += w
            if idx < len(order) - 1:
                x += gap_w
                joint_widths.append(round(gap_w, 2))

    prev_joints: list[float] = []
    blocked_next: list[tuple[float, float]] = []
    course_bottom = max_y
    course_index = 0
    safety = 0

    while course_bottom > min_y + 1.0 and safety < 400:
        safety += 1
        avail = available()
        if not avail:
            break
        shorts = [min(s["width_cm"], s["height_cm"]) for s in avail]
        band = _choose_band_height(shorts, rng)
        band = min(band, course_bottom - min_y)
        if band < _MIN_STONE_CM:
            break  # top sliver below any stone height: leave as a trim zone

        course_top = course_bottom - band
        mid_y = (course_bottom + course_top) / 2.0
        intervals = region_intervals_at(mid_y, walls, negs)
        intervals = subtract_intervals(intervals, blocked_next)

        this_joints: list[float] = []
        new_blocked: list[tuple[float, float]] = []
        # prev_joints is read inside fill via closure; bind current course's below-joints
        prev_for_course = prev_joints
        for x_left, x_right in intervals:
            fill(x_left, x_right, course_bottom, band, course_index, this_joints, new_blocked)

        prev_joints = sorted(this_joints)
        blocked_next = new_blocked
        course_bottom = course_top
        course_index += 1
        _ = prev_for_course

    report = _build_report(placements, stones, walls, negs, cuts, gaps, joint_widths, course_index)
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


def _build_report(placements, stones, walls, negs, cuts, gaps, joints, courses):
    placed_area = sum(p["w_cm"] * p["h_cm"] for p in placements)
    net = _net_wall_area(walls, negs)
    return {
        "coverage_pct": round(100.0 * placed_area / net, 1) if net > 0 else 0.0,
        "stones_used": len(placements),
        "stones_available": len(stones),
        "courses": courses,
        "cut_count": len(cuts),
        "cut_total_cm": round(sum(cuts), 1),
        "gap_count": len(gaps),
        "gap_total_cm": round(sum(gaps), 1),
        "joint_min_cm": round(min(joints), 2) if joints else 0.0,
        "joint_max_cm": round(max(joints), 2) if joints else 0.0,
        "joint_mean_cm": round(sum(joints) / len(joints), 2) if joints else 0.0,
    }
