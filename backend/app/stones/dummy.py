import random

from app.geometry import polygon_area_cm2


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _jitter_rect(w: float, h: float, jitter: float, rng: random.Random) -> list[list[float]]:
    """A near-rectangle in local coords [0..w] x [0..h] with jittered corners."""
    def j() -> float:
        return rng.uniform(-jitter, jitter)

    return [
        [round(max(0.0, 0 + j()), 2), round(max(0.0, 0 + j()), 2)],
        [round(w + j(), 2), round(max(0.0, 0 + j()), 2)],
        [round(w + j(), 2), round(h + j(), 2)],
        [round(max(0.0, 0 + j()), 2), round(h + j(), 2)],
    ]


def generate_dummy_stone_dicts(
    count: int,
    seed: int,
    mean_w: float = 30.0,
    mean_h: float = 13.0,
    spread: float = 6.0,
    min_side: float = 10.0,
    max_side: float = 40.0,
    jitter: float = 0.6,
) -> list[dict]:
    """Seedable near-rectangular stones matching the real size profile."""
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        w = _clamp(rng.gauss(mean_w, spread), min_side, max_side)
        h = _clamp(rng.gauss(mean_h, spread * 0.6), min_side, max_side)
        if h > w:
            w, h = h, w  # width is the longer side
        poly = _jitter_rect(w, h, jitter, rng)
        out.append(
            {
                "width_cm": round(w, 1),
                "height_cm": round(h, 1),
                "polygon": poly,
                "area_cm2": round(polygon_area_cm2(poly), 1),
            }
        )
    return out
