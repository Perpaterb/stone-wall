from app.geometry import polygon_area_cm2
from app.solver.geometry import (
    polygon_intervals_at,
    region_intervals_at,
    subtract_intervals,
    union_intervals,
)


def test_polygon_area_rectangle():
    assert polygon_area_cm2([[0, 0], [10, 0], [10, 5], [0, 5]]) == 50.0


def test_polygon_area_degenerate():
    assert polygon_area_cm2([[0, 0], [10, 0]]) == 0.0


def test_intervals_at_rectangle():
    poly = [[0, 0], [100, 0], [100, 50], [0, 50]]
    assert polygon_intervals_at(poly, 25) == [(0.0, 100.0)]


def test_union_intervals_merges():
    assert union_intervals([(0, 10), (5, 15), (20, 25)]) == [(0, 15), (20, 25)]


def test_subtract_intervals_punches_hole():
    assert subtract_intervals([(0, 100)], [(40, 60)]) == [(0, 40), (60, 100)]


def test_region_subtracts_negative():
    wall = [[0, 0], [100, 0], [100, 100], [0, 100]]
    neg = [[40, 40], [60, 40], [60, 60], [40, 60]]
    # A scanline through the negative splits the wall into two pieces.
    ivs = region_intervals_at(50, [wall], [neg])
    assert ivs == [(0.0, 40.0), (60.0, 100.0)]
    # A scanline above the negative is a single interval.
    assert region_intervals_at(10, [wall], [neg]) == [(0.0, 100.0)]
