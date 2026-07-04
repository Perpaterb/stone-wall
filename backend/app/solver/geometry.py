"""1D interval math over a horizontal scanline through the wall region.

The solver fills the wall course by course. For each course it takes a
horizontal line at the course mid-height and asks: which x-ranges are inside a
wall polygon and not inside a negative polygon? Those ranges are what we fill.
"""


def polygon_intervals_at(poly: list[list[float]], y: float) -> list[tuple[float, float]]:
    """X-ranges where the horizontal line at `y` is inside `poly`."""
    xs: list[float] = []
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        # Half-open test so a vertex shared by two edges is counted once.
        if (y1 <= y < y2) or (y2 <= y < y1):
            t = (y - y1) / (y2 - y1)
            xs.append(x1 + t * (x2 - x1))
    xs.sort()
    return [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]


def union_intervals(ivs: list[tuple[float, float]]) -> list[tuple[float, float]]:
    ivs = sorted(ivs)
    out: list[tuple[float, float]] = []
    for s, e in ivs:
        if out and s <= out[-1][1] + 1e-9:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def subtract_intervals(
    a: list[tuple[float, float]], b: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for s, e in a:
        segs = [(s, e)]
        for bs, be in b:
            nxt: list[tuple[float, float]] = []
            for cs, ce in segs:
                if be <= cs or bs >= ce:
                    nxt.append((cs, ce))
                    continue
                if cs < bs:
                    nxt.append((cs, bs))
                if be < ce:
                    nxt.append((be, ce))
            segs = nxt
        result.extend(segs)
    return [(s, e) for s, e in result if e - s > 0.01]


def region_intervals_at(
    y: float, walls: list[list[list[float]]], negs: list[list[list[float]]]
) -> list[tuple[float, float]]:
    wall_iv = union_intervals([iv for w in walls for iv in polygon_intervals_at(w, y)])
    neg_iv = union_intervals([iv for n in negs for iv in polygon_intervals_at(n, y)])
    return subtract_intervals(wall_iv, neg_iv)
