"""Rustic wall packing solver (v1).

Fills the wall region course by course from the bottom up. Within each course
it lays stones left to right, distributing grout slack, staggering vertical
joints against the course below, occasionally standing a tall stone as a
through-stone spanning two courses, and flagging a cut where a stone must be
trimmed to meet a wall edge. Packs by bounding box; true shapes are rendered.

Coordinates are the plan's (y increases downward), so the wall bottom is the
largest y and courses climb toward the smallest y.
"""

import random

from app.solver.geometry import region_intervals_at, subtract_intervals


def _orient(width_cm: float, height_cm: float, target: float, tol: float):
    """Pick an orientation whose vertical side is within [target-2tol, target].

    Returns (horizontal, vertical, rotation_deg) or None. rotation_deg is 0 when
    the stored height side is vertical, 90 when the stone is stood on its end.
    """
    best = None
    for horiz, vert, rot in ((width_cm, height_cm, 0.0), (height_cm, width_cm, 90.0)):
        if target - 2 * tol <= vert <= target:
            score = target - vert
            if best is None or score < best[0]:
                best = (score, horiz, vert, rot)
    if best is None:
        return None
    return best[1], best[2], best[3]


def _orient_through(width_cm: float, height_cm: float, target2: float, tol: float):
    for horiz, vert, rot in ((width_cm, height_cm, 0.0), (height_cm, width_cm, 90.0)):
        if target2 - tol <= vert <= target2 + tol:
            return horiz, vert, rot
    return None


def _choose_band_height(short_sides: list[float], rng: random.Random) -> float:
    hs = sorted(short_sides)
    lo = hs[int(len(hs) * 0.25)]
    hi = hs[int(len(hs) * 0.75)]
    return max(8.0, rng.uniform(lo, hi))


def solve(walls, negs, stones, params):
    rng = random.Random(params.get("seed", 0))
    gmin = params.get("grout_min_cm", 1.0)
    gmax = params.get("grout_max_cm", 3.0)
    gt = (gmin + gmax) / 2.0
    stagger = params.get("stagger_min_cm", 6.0)
    tol = params.get("band_tol_cm", 5.0)
    through_prob = params.get("through_stone_prob", 0.08)

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

    prev_joints: list[float] = []
    blocked_next: list[tuple[float, float]] = []
    course_bottom = max_y
    course_index = 0
    safety = 0

    def available():
        return [s for sid, s in pool.items() if sid not in used]

    while course_bottom > min_y + 1.0 and safety < 400:
        safety += 1
        avail = available()
        if not avail:
            break
        short_sides = [min(s["width_cm"], s["height_cm"]) for s in avail]
        band = _choose_band_height(short_sides, rng)
        band = min(band, course_bottom - min_y)
        if band < 6.0:
            band = course_bottom - min_y
        course_top = course_bottom - band
        mid_y = (course_bottom + course_top) / 2.0

        intervals = region_intervals_at(mid_y, walls, negs)
        intervals = subtract_intervals(intervals, blocked_next)

        this_joints: list[float] = []
        new_blocked: list[tuple[float, float]] = []

        for x_left, x_right in intervals:
            x = x_left
            this_joints.append(round(x, 2))
            guard = 0
            while x < x_right - 0.5 and guard < 500:
                guard += 1
                remaining = x_right - x

                # Occasionally stand a tall stone as a through-stone, but only
                # when a full further course fits above it (else it pokes past
                # the wall top).
                if (
                    rng.random() < through_prob
                    and remaining > band
                    and course_bottom - 2 * band >= min_y
                ):
                    tstone = None
                    for s in available():
                        ori = _orient_through(s["width_cm"], s["height_cm"], 2 * band, tol)
                        if (
                            ori
                            and ori[0] <= remaining - gmin
                            and course_bottom - ori[1] >= min_y - 0.5
                        ):
                            tstone = (s, ori)
                            break
                    if tstone:
                        s, (w, h, rot) = tstone
                        placements.append(_place(s, x, course_bottom - h, w, h, rot, course_index, None))
                        used.add(s["id"])
                        new_blocked.append((x, x + w))
                        joint = x + w
                        this_joints.append(round(joint, 2))
                        joint_widths.append(gt)
                        x = joint + gt
                        continue

                # Candidate stones oriented to this course band.
                cands = []
                for s in available():
                    ori = _orient(s["width_cm"], s["height_cm"], band, tol)
                    if ori:
                        cands.append((s, ori))

                fit = [c for c in cands if c[1][0] <= remaining - gmin + 0.01]
                if not fit:
                    # Nothing fits the remaining space without a cut.
                    if remaining <= gmax:
                        break  # just mortar slack
                    cut_cands = sorted(
                        (c for c in cands if c[1][0] > remaining),
                        key=lambda c: c[1][0],
                    )
                    if cut_cands:
                        s, (w, h, rot) = cut_cands[0]
                        kept = remaining
                        placements.append(
                            _place(s, x, course_bottom - h, kept, h, rot, course_index,
                                   {"needed": True, "from": "right", "removed_cm": round(w - kept, 1)})
                        )
                        used.add(s["id"])
                        cuts.append(w - kept)
                        this_joints.append(round(x + kept, 2))
                        x = x_right
                    else:
                        gaps.append(remaining)
                        x = x_right
                    break

                # Prefer widths that do not create a running joint with the course below.
                def running(jx: float) -> bool:
                    return any(abs(jx - pj) < stagger for pj in prev_joints)

                good = [c for c in fit if not running(x + c[1][0])]
                choose_from = good if good else fit
                choose_from.sort(key=lambda c: -c[1][0])
                top = choose_from[: min(4, len(choose_from))]
                s, (w, h, rot) = rng.choice(top)

                placements.append(_place(s, x, course_bottom - h, w, h, rot, course_index, None))
                used.add(s["id"])
                joint = x + w
                this_joints.append(round(joint, 2))
                joint_widths.append(gt)
                x = joint + gt

        prev_joints = sorted(this_joints)
        blocked_next = new_blocked
        course_bottom = course_top
        course_index += 1

    report = _build_report(
        placements, stones, walls, negs, cuts, gaps, joint_widths, course_index
    )
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
