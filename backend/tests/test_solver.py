from collections import defaultdict

from app.solver.packer import solve
from app.stones.dummy import generate_dummy_stone_dicts


def _stones(n, seed):
    return [
        {
            "id": i,
            "code": f"S{i:04d}",
            "width_cm": d["width_cm"],
            "height_cm": d["height_cm"],
            "polygon": d["polygon"],
        }
        for i, d in enumerate(generate_dummy_stone_dicts(n, seed))
    ]


def _bounds(walls):
    pts = [p for w in walls for p in w]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), max(xs), min(ys), max(ys)


def _assert_valid(walls, negs, placements):
    minx, maxx, miny, maxy = _bounds(walls)
    for p in placements:
        assert p["x_cm"] >= minx - 0.5
        assert p["x_cm"] + p["w_cm"] <= maxx + 0.5
        assert p["y_cm"] >= miny - 0.5
        assert p["y_cm"] + p["h_cm"] <= maxy + 0.5
    by_course = defaultdict(list)
    for p in placements:
        by_course[p["course_index"]].append((p["x_cm"], p["x_cm"] + p["w_cm"]))
    for ranges in by_course.values():
        ranges.sort()
        for a, b in zip(ranges, ranges[1:]):
            assert b[0] >= a[1] - 0.01, "stones overlap within a course"


def test_rectangular_wall():
    walls = [[[0, 0], [300, 0], [300, 270], [0, 270]]]
    placements, report = solve(
        walls, [], _stones(500, 1), {"seed": 1, "grout_min_cm": 1.0, "grout_max_cm": 3.0}
    )
    _assert_valid(walls, [], placements)
    assert report["stones_used"] > 0
    # With ample stones the wall fills well; a thin top sliver may remain as a
    # reported gap (hand-cut top course), which is expected, so we do not require
    # zero gaps here.
    assert report["coverage_pct"] > 70


def test_angled_top_wall():
    walls = [[[0, 60], [400, 0], [400, 270], [0, 270]]]
    placements, report = solve(
        walls, [], _stones(600, 2), {"seed": 2, "grout_min_cm": 1.0, "grout_max_cm": 3.0}
    )
    _assert_valid(walls, [], placements)
    assert report["stones_used"] > 0


def test_wall_with_negative():
    walls = [[[0, 0], [300, 0], [300, 270], [0, 270]]]
    negs = [[[120, 120], [180, 120], [180, 180], [120, 180]]]
    placements, _ = solve(
        walls, negs, _stones(500, 3), {"seed": 3, "grout_min_cm": 1.0, "grout_max_cm": 3.0}
    )
    _assert_valid(walls, negs, placements)
    # No stone centre should sit inside the negative area.
    for p in placements:
        cx = p["x_cm"] + p["w_cm"] / 2
        cy = p["y_cm"] + p["h_cm"] / 2
        inside_neg = 120 < cx < 180 and 120 < cy < 180
        assert not inside_neg


def test_reports_gaps_when_stones_run_out():
    walls = [[[0, 0], [1200, 0], [1200, 270], [0, 270]]]
    _, report = solve(
        walls, [], _stones(80, 4), {"seed": 4, "grout_min_cm": 1.0, "grout_max_cm": 3.0}
    )
    assert report["stones_used"] <= 80
    assert report["gap_count"] > 0


def test_no_stones_returns_nothing():
    walls = [[[0, 0], [100, 0], [100, 100], [0, 100]]]
    placements, report = solve(walls, [], [], {"seed": 1})
    assert placements == []
