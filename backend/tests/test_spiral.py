from app.solver.packer_spiral import solve_spiral
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


def _no_overlap(placements):
    for i in range(len(placements)):
        a = placements[i]
        ax0, ay0, ax1, ay1 = a["x_cm"], a["y_cm"], a["x_cm"] + a["w_cm"], a["y_cm"] + a["h_cm"]
        for j in range(i + 1, len(placements)):
            b = placements[j]
            bx0, by0, bx1, by1 = b["x_cm"], b["y_cm"], b["x_cm"] + b["w_cm"], b["y_cm"] + b["h_cm"]
            if min(ax1, bx1) - max(ax0, bx0) > 0.5 and min(ay1, by1) - max(ay0, by0) > 0.5:
                return False
    return True


def test_spiral_fills_without_overlap():
    walls = [[[0, 0], [200, 0], [200, 150], [0, 150]]]
    placements, report, _ = solve_spiral(
        walls, [], _stones(400, 1), {"seed": 3, "cell_cm": 0.5, "seeds": 3, "allow_edge_cut": False}
    )
    assert report["stones_used"] > 10
    assert report["coverage_pct"] > 60
    assert _no_overlap(placements)
    for p in placements:
        assert -0.5 <= p["x_cm"] and p["x_cm"] + p["w_cm"] <= 200.5
        assert -0.5 <= p["y_cm"] and p["y_cm"] + p["h_cm"] <= 150.5


def test_spiral_respects_negative():
    walls = [[[0, 0], [200, 0], [200, 150], [0, 150]]]
    negs = [[[80, 60], [120, 60], [120, 90], [80, 90]]]
    placements, _, _ = solve_spiral(
        walls, negs, _stones(400, 2), {"seed": 5, "cell_cm": 0.5, "seeds": 3, "allow_edge_cut": False}
    )
    assert _no_overlap(placements)
    for p in placements:
        cx = p["x_cm"] + p["w_cm"] / 2
        cy = p["y_cm"] + p["h_cm"] / 2
        assert not (80 < cx < 120 and 60 < cy < 90)


def test_spiral_no_stones():
    placements, report, _ = solve_spiral([[[0, 0], [100, 0], [100, 100], [0, 100]]], [], [], {})
    assert placements == []
