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

import numpy as np

from app.solver.geometry import region_intervals_at

# Bump when the algorithm changes so the UI can show which version ran.
VERSION = "spiral-5 (clockwise angular sweep, edge-cut, 50/50 rot)"
BEAM_VERSION = "beam-6 (beam-5 + compaction pass to close small holes)"


def _orientations(stone):
    w = stone["width_cm"]
    h = stone["height_cm"]
    yield w, h, 0.0
    if abs(w - h) > 0.1:
        yield h, w, 90.0


def solve_spiral(walls, negs, stones, params):
    rng = random.Random(params.get("seed", 0))
    cell = params.get("cell_cm", 0.5)
    gmax = params.get("grout_max_cm", 0.3)
    n_seeds = int(params.get("seeds", 4))

    if not walls or not stones:
        return [], _empty_report(len(stones)), []

    pts = [p for w in walls for p in w]
    min_x = min(p[0] for p in pts)
    max_x = max(p[0] for p in pts)
    min_y = min(p[1] for p in pts)
    max_y = max(p[1] for p in pts)

    # A stone may overhang the wall edge and get cut, as long as at least
    # min_inside of it stays inside. Pad the grid so overhang has room.
    # mode: "spiral" = clockwise angular sweep; "beam" = fill nearest empty spot.
    mode = params.get("mode", "spiral")
    allow_edge = params.get("allow_edge_cut", True)
    if mode == "beam":
        # Beam mode does not restrict overhang at all.
        allow_edge = True
        min_inside = params.get("min_inside_frac", 0.0)
        pad = 42.0
    else:
        min_inside = params.get("min_inside_frac", 0.5)
        pad = 22.0 if allow_edge else 0.0
    ox = min_x - pad
    oy = min_y - pad

    cols = max(1, int(math.ceil((max_x + pad - ox) / cell)))
    rows = max(1, int(math.ceil((max_y + pad - oy) / cell)))

    inside = np.zeros((rows, cols), dtype=bool)
    for r in range(rows):
        y = oy + (r + 0.5) * cell
        for x0, x1 in region_intervals_at(y, walls, negs):
            c0 = max(0, int(math.floor((x0 - ox) / cell)))
            c1 = min(cols, int(math.ceil((x1 - ox) / cell)))
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
        if not (occ[r0:r1, c0:c1] == 0).all():
            return False
        ins = inside[r0:r1, c0:c1]
        if allow_edge:
            # Enough of the footprint inside the wall; the rest is a cut edge.
            return bool(ins.mean() >= min_inside)
        return bool(ins.all())

    def place(idx, r0, r1, c0, c1, w, h, rot):
        occ[r0:r1, c0:c1] = idx + 1
        used.add(idx)
        x = ox + c0 * cell
        y = oy + r0 * cell
        course = int((max_y - (y + h)) / 12)
        frac_in = float(inside[r0:r1, c0:c1].mean())
        cut = (
            None
            if frac_in > 0.995
            else {"needed": True, "reason": "wall edge", "inside_frac": round(frac_in, 2)}
        )
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
                "cut": cut,
                "_idx": idx,
                "_r0": r0,
                "_r1": r1,
                "_c0": c0,
                "_c1": c1,
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

    counts = [0, 0]  # placed [landscape (rot 0), portrait (rot 90)]

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
            fit = []
            for w, h, rot, wc, hc in ori[i]:
                c0 = c if sc > 0 else c + 1 - wc
                r0 = r if sr > 0 else r + 1 - hc
                if fits(r0, r0 + hc, c0, c0 + wc):
                    fit.append((i, r0, r0 + hc, c0, c0 + wc, w, h, rot))
            if not fit:
                continue
            # When both orientations fit, keep the under-represented one so the
            # wall reads ~50/50 portrait/landscape instead of all wide.
            if len(fit) == 2:
                fit.sort(key=lambda o: counts[1 if o[7] == 90 else 0])
            found.append(fit[0])
            if len(found) >= 6:
                break
        if not found:
            return None
        # Prefer the under-represented orientation among the fitting candidates.
        desired = 0 if counts[0] <= counts[1] else 1
        pref = [f for f in found if (1 if f[7] == 90 else 0) == desired]
        chosen = rng.choice(pref) if pref and rng.random() < 0.7 else rng.choice(found)
        i, r0, r1, c0, c1, w, h, rot = chosen
        place(i, r0, r1, c0, c1, w, h, rot)
        counts[1 if rot == 90 else 0] += 1
        return r0, r1, c0, c1

    def place_flush(r, c):
        """Place a stone flush against the cluster wall at the beam point.

        Finds which side the cluster is on, presses the stone's edge flush against
        that wall (not corner-anchored), slides it along the wall to cover the beam
        point, and prefers the orientation that puts the stone's long side along
        the constraint. Fills 3-sided pockets because only a fitting stone passes.
        """
        if c > 0 and occ[r, c - 1] > 0:
            side = "L"
        elif c + 1 < cols and occ[r, c + 1] > 0:
            side = "R"
        elif r > 0 and occ[r - 1, c] > 0:
            side = "U"
        elif r + 1 < rows and occ[r + 1, c] > 0:
            side = "D"
        else:
            return None
        vertical = side in ("L", "R")

        # Extent of the cluster wall along the boundary (constraint length).
        if vertical:
            wcol = c - 1 if side == "L" else c + 1
            a, b = r, r
            while a - 1 >= 0 and occ[a - 1, wcol] > 0:
                a -= 1
            while b + 1 < rows and occ[b + 1, wcol] > 0:
                b += 1
        else:
            wrow = r - 1 if side == "U" else r + 1
            a, b = c, c
            while a - 1 >= 0 and occ[wrow, a - 1] > 0:
                a -= 1
            while b + 1 < cols and occ[wrow, b + 1] > 0:
                b += 1

        def slides(size, cover):
            cand = [(a + b) // 2 - size // 2, a, b + 1 - size, cover - size // 2, cover, cover - size + 1]
            out, seen = [], set()
            for p in cand:
                if p in seen:
                    continue
                seen.add(p)
                if p <= cover < p + size:
                    out.append(p)
            return out

        def contact_v(r0, r1, wc_):
            if wc_ < 0 or wc_ >= cols:
                return 0
            return int((occ[max(0, r0):min(rows, r1), wc_] > 0).sum())

        def contact_h(c0, c1, wr_):
            if wr_ < 0 or wr_ >= rows:
                return 0
            return int((occ[wr_, max(0, c0):min(cols, c1)] > 0).sum())

        def try_stone(wc, hc):
            if side == "L":
                c0, c1 = c, c + wc
                for r0 in slides(hc, r):
                    if fits(r0, r0 + hc, c0, c1) and contact_v(r0, r0 + hc, c - 1) > 0:
                        return (r0, r0 + hc, c0, c1)
            elif side == "R":
                c1, c0 = c + 1, c + 1 - wc
                for r0 in slides(hc, r):
                    if fits(r0, r0 + hc, c0, c1) and contact_v(r0, r0 + hc, c + 1) > 0:
                        return (r0, r0 + hc, c0, c1)
            elif side == "U":
                r0, r1 = r, r + hc
                for c0 in slides(wc, c):
                    if fits(r0, r1, c0, c0 + wc) and contact_h(c0, c0 + wc, r - 1) > 0:
                        return (r0, r1, c0, c0 + wc)
            else:  # D
                r1, r0 = r + 1, r + 1 - hc
                for c0 in slides(wc, c):
                    if fits(r0, r1, c0, c0 + wc) and contact_h(c0, c0 + wc, r + 1) > 0:
                        return (r0, r1, c0, c0 + wc)
            return None

        def long_first(o):
            _, _, _, wc, hc = o
            long_along = (hc >= wc) if vertical else (wc >= hc)
            return 0 if long_along else 1

        found = []
        scanned = 0
        for i in order:
            if i in used:
                continue
            if scanned > 150:
                break
            scanned += 1
            for w, h, rot, wc, hc in sorted(ori[i], key=long_first):
                pos = try_stone(wc, hc)
                if pos:
                    found.append((i, pos, w, h, rot))
                    break
            if len(found) >= 5:
                break
        if not found:
            return None
        i, (r0, r1, c0, c1), w, h, rot = rng.choice(found)
        place(i, r0, r1, c0, c1, w, h, rot)
        counts[1 if rot == 90 else 0] += 1
        return r0, r1, c0, c1

    min_gap = max(1, int(round(5.0 / cell)))  # 5 cm = smallest fillable gap

    def no_sliver(r0, r1, c0, c1):
        """True unless placing [r0:r1,c0:c1] leaves a 0<gap<5cm sliver to an
        existing stone on any side. A side is fine if the immediately adjacent
        cell is occupied (flush) or nothing sits within 5cm (open); a sliver is
        an empty adjacent cell with an occupied cell just beyond it."""
        # left
        if c0 - 1 >= 0 and c0 - 1 > max(0, c0 - min_gap):
            adj = occ[r0:r1, c0 - 1] == 0
            zone = occ[r0:r1, max(0, c0 - min_gap):c0 - 1] > 0
            if zone.size and bool((adj & zone.any(axis=1)).any()):
                return False
        # right
        if c1 < cols and min(cols, c1 + min_gap) > c1 + 1:
            adj = occ[r0:r1, c1] == 0
            zone = occ[r0:r1, c1 + 1:min(cols, c1 + min_gap)] > 0
            if zone.size and bool((adj & zone.any(axis=1)).any()):
                return False
        # up
        if r0 - 1 >= 0 and r0 - 1 > max(0, r0 - min_gap):
            adj = occ[r0 - 1, c0:c1] == 0
            zone = occ[max(0, r0 - min_gap):r0 - 1, c0:c1] > 0
            if zone.size and bool((adj & zone.any(axis=0)).any()):
                return False
        # down
        if r1 < rows and min(rows, r1 + min_gap) > r1 + 1:
            adj = occ[r1, c0:c1] == 0
            zone = occ[r1 + 1:min(rows, r1 + min_gap), c0:c1] > 0
            if zone.size and bool((adj & zone.any(axis=0)).any()):
                return False
        return True

    def place_beam5(r, c):
        """Flush placement that also refuses to leave a <5cm sliver. Slides the
        stone along the wall to a position whose end gaps are 0 or >=5cm, and
        rejects any placement that would sit a sliver away from another stone."""
        occL = c > 0 and occ[r, c - 1] > 0
        occR = c + 1 < cols and occ[r, c + 1] > 0
        occU = r > 0 and occ[r - 1, c] > 0
        occD = r + 1 < rows and occ[r + 1, c] > 0
        if not (occL or occR or occU or occD):
            return None

        vr0 = vr1 = hcc0 = hcc1 = None
        if occL or occR:
            a = b = r
            while a - 1 >= 0 and occ[a - 1, c] == 0:
                a -= 1
            while b + 1 < rows and occ[b + 1, c] == 0:
                b += 1
            vr0, vr1 = a, b
        if occU or occD:
            a = b = c
            while a - 1 >= 0 and occ[r, a - 1] == 0:
                a -= 1
            while b + 1 < cols and occ[r, b + 1] == 0:
                b += 1
            hcc0, hcc1 = a, b

        def positions(size, s0, s1, cover):
            lo = max(s0, cover - size + 1)
            hi = min(cover, s1 + 1 - size)
            out = []
            for p in (s0, s1 + 1 - size, cover - size // 2, cover, cover - size + 1):
                if p < lo or p > hi:
                    continue
                gtop = p - s0
                gbot = (s1 + 1) - (p + size)
                if (gtop == 0 or gtop >= min_gap) and (gbot == 0 or gbot >= min_gap):
                    out.append(p)
            return out

        cands = []
        scanned = 0
        for i in order:
            if i in used:
                continue
            if scanned > 200:
                break
            scanned += 1
            got = None
            for w, h, rot, wc, hc in ori[i]:
                if (occL or occR) and vr0 is not None and hc <= vr1 - vr0 + 1:
                    c0, c1 = (c, c + wc) if occL else (c + 1 - wc, c + 1)
                    for r0 in positions(hc, vr0, vr1, r):
                        if fits(r0, r0 + hc, c0, c1) and no_sliver(r0, r0 + hc, c0, c1):
                            got = (r0, r0 + hc, c0, c1, w, h, rot)
                            break
                if got is None and (occU or occD) and hcc0 is not None and wc <= hcc1 - hcc0 + 1:
                    r0, r1 = (r, r + hc) if occU else (r + 1 - hc, r + 1)
                    for c0 in positions(wc, hcc0, hcc1, c):
                        if fits(r0, r1, c0, c0 + wc) and no_sliver(r0, r1, c0, c0 + wc):
                            got = (r0, r1, c0, c0 + wc, w, h, rot)
                            break
                if got:
                    break
            if got:
                cands.append((i, got))
                if len(cands) >= 6:
                    break
        if not cands:
            # Nothing fits here without leaving a <5cm sliver: leave the spot empty
            # (a >=5cm fillable gap is fine; a thin unfillable sliver is not).
            return None
        i, (r0, r1, c0, c1, w, h, rot) = rng.choice(cands)
        place(i, r0, r1, c0, c1, w, h, rot)
        counts[1 if rot == 90 else 0] += 1
        return r0, r1, c0, c1

    grout_cells = max(1, int(round(gmax / cell)))

    def _components(r0, r1, c0, c1):
        """Empty-inside connected components in a window: list of bad-gap bboxes
        (min dim > grout, < 5cm), and the total cell count of those. Iterates
        only the empty cells so it stays cheap."""
        r0 = max(0, r0); r1 = min(rows, r1); c0 = max(0, c0); c1 = min(cols, c1)
        if r1 <= r0 or c1 <= c0:
            return [], 0
        sub = inside[r0:r1, c0:c1] & (occ[r0:r1, c0:c1] == 0)
        seen = np.zeros_like(sub)
        hh, ww = sub.shape
        bad_cells = 0
        boxes = []
        for y, x in np.argwhere(sub):
            if seen[y, x]:
                continue
            st = [(y, x)]
            seen[y, x] = True
            cells = []
            while st:
                a, b = st.pop()
                cells.append((a, b))
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    na, nb = a + da, b + db
                    if 0 <= na < hh and 0 <= nb < ww and sub[na, nb] and not seen[na, nb]:
                        seen[na, nb] = True
                        st.append((na, nb))
            ys = [a for a, b in cells]
            xs = [b for a, b in cells]
            md = min(max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)
            if grout_cells < md < min_gap:
                bad_cells += len(cells)
                boxes.append((r0 + min(ys), r0 + max(ys) + 1, c0 + min(xs), c0 + max(xs) + 1))
        return boxes, bad_cells

    def _try_shift(seed, dr, dc):
        """Shift a stone group by (dr,dc) cells to close a hole, only if it does
        not overlap and it reduces the local bad-gap area; else roll back."""
        idx_to_k = {placements[k2]["_idx"]: k2 for k2 in range(len(placements))}
        group = set(seed)
        guard = 0
        changed = True
        while changed and len(group) <= 8 and guard < 30:
            guard += 1
            changed = False
            for k in list(group):
                p = placements[k]
                nr0, nr1, nc0, nc1 = p["_r0"] + dr, p["_r1"] + dr, p["_c0"] + dc, p["_c1"] + dc
                if nr0 < 0 or nc0 < 0 or nr1 > rows or nc1 > cols:
                    return False
                for v in np.unique(occ[nr0:nr1, nc0:nc1]):
                    if v == 0:
                        continue
                    j = idx_to_k.get(int(v) - 1)
                    if j is not None and j not in group:
                        group.add(j)
                        changed = True
        if len(group) > 8:
            return False
        old = {k: (placements[k]["_r0"], placements[k]["_r1"], placements[k]["_c0"], placements[k]["_c1"], placements[k]["_idx"]) for k in group}
        wr0 = min(v[0] for v in old.values()) + min(dr, 0) - min_gap
        wr1 = max(v[1] for v in old.values()) + max(dr, 0) + min_gap
        wc0 = min(v[2] for v in old.values()) + min(dc, 0) - min_gap
        wc1 = max(v[3] for v in old.values()) + max(dc, 0) + min_gap
        _, before = _components(wr0, wr1, wc0, wc1)
        for k in group:
            r0, r1, c0, c1, _ = old[k]
            occ[r0:r1, c0:c1] = 0
        overlap = False
        for k in group:
            r0, r1, c0, c1, _ = old[k]
            if (occ[r0 + dr:r1 + dr, c0 + dc:c1 + dc] != 0).any():
                overlap = True
                break
        if overlap:
            for k in group:
                r0, r1, c0, c1, idx = old[k]
                occ[r0:r1, c0:c1] = idx + 1
            return False
        for k in group:
            r0, r1, c0, c1, idx = old[k]
            occ[r0 + dr:r1 + dr, c0 + dc:c1 + dc] = idx + 1
        _, after = _components(wr0, wr1, wc0, wc1)
        if after < before:
            for k in group:
                r0, r1, c0, c1, idx = old[k]
                p = placements[k]
                p["_r0"], p["_r1"], p["_c0"], p["_c1"] = r0 + dr, r1 + dr, c0 + dc, c1 + dc
                p["x_cm"] = round(ox + (c0 + dc) * cell, 2)
                p["y_cm"] = round(oy + (r0 + dr) * cell, 2)
            return True
        for k in group:
            r0, r1, c0, c1, idx = old[k]
            occ[r0 + dr:r1 + dr, c0 + dc:c1 + dc] = 0
        for k in group:
            r0, r1, c0, c1, idx = old[k]
            occ[r0:r1, c0:c1] = idx + 1
        return False

    def compact(wr0=0, wr1=None, wc0=0, wc1=None):
        wr1 = rows if wr1 is None else wr1
        wc1 = cols if wc1 is None else wc1
        boxes, _ = _components(wr0, wr1, wc0, wc1)
        for r0, r1, c0, c1 in boxes:
            bw, bh = c1 - c0, r1 - r0
            if bw <= bh:
                right = {j for j, q in enumerate(placements) if q["_c0"] == c1 and q["_r0"] < r1 and r0 < q["_r1"]}
                left = {j for j, q in enumerate(placements) if q["_c1"] == c0 and q["_r0"] < r1 and r0 < q["_r1"]}
                if right and _try_shift(right, 0, -bw):
                    continue
                if left and _try_shift(left, 0, bw):
                    continue
            else:
                down = {j for j, q in enumerate(placements) if q["_r0"] == r1 and q["_c0"] < c1 and c0 < q["_c1"]}
                up = {j for j, q in enumerate(placements) if q["_r1"] == r0 and q["_c0"] < c1 and c0 < q["_c1"]}
                if down and _try_shift(down, -bh, 0):
                    continue
                if up and _try_shift(up, bh, 0):
                    continue

    frontier: set = set()

    def add_frontier(r0, r1, c0, c1):
        for cc in range(c0 - 1, c1 + 1):
            for rr in (r0 - 1, r1):
                if 0 <= rr < rows and 0 <= cc < cols and inside[rr, cc] and occ[rr, cc] == 0:
                    frontier.add((rr, cc))
        for rr in range(r0 - 1, r1 + 1):
            for cc in (c0 - 1, c1):
                if 0 <= rr < rows and 0 <= cc < cols and inside[rr, cc] and occ[rr, cc] == 0:
                    frontier.add((rr, cc))

    # Seed stones at random valid points (multiple nucleation sites).
    seed_points: list[list[float]] = []
    tries = 0
    while len(seed_points) < n_seeds and tries < n_seeds * 80:
        tries += 1
        r = rng.randrange(rows)
        c = rng.randrange(cols)
        if not inside[r, c] or occ[r, c] != 0:
            continue
        if mode == "beam":
            # Beam: the seed point is the beam origin; the BIGGEST available stone
            # is placed so the seed point sits INSIDE it, off-centre (not the exact
            # centre, not on an edge).
            idx = next((i for i in order if i not in used), None)
            if idx is None:
                break
            w, h, rot, wc, hc = ori[idx][0]
            fr = rng.choice([rng.uniform(0.28, 0.42), rng.uniform(0.58, 0.72)])
            fc = rng.choice([rng.uniform(0.28, 0.42), rng.uniform(0.58, 0.72)])
            r0 = r - int(round(hc * fr))
            c0 = c - int(round(wc * fc))
            if fits(r0, r0 + hc, c0, c0 + wc):
                place(idx, r0, r0 + hc, c0, c0 + wc, w, h, rot)
                add_frontier(r0, r0 + hc, c0, c0 + wc)
                seed_points.append(
                    [round(ox + (c + 0.5) * cell, 1), round(oy + (r + 0.5) * cell, 1)]
                )
        else:
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
                add_frontier(r0, r0 + hc, c0, c0 + wc)
                cx = ox + (c0 + wc / 2) * cell
                cy = oy + (r0 + hc / 2) * cell
                seed_points.append([round(cx, 1), round(cy, 1)])

    # Grow in a CLOCKWISE SPIRAL around the seed(s). Each step picks the frontier
    # cell that is the next one clockwise from the current sweep angle (inner
    # radius first), so stones wind around the cluster in order instead of the
    # jumpy breadth-first fill. With y down, increasing atan2 angle sweeps
    # east -> south -> west -> north, i.e. clockwise.
    if seed_points:
        sx = sum(p[0] for p in seed_points) / len(seed_points)
        sy = sum(p[1] for p in seed_points) / len(seed_points)
    else:
        sx, sy = (min_x + max_x) / 2.0, (min_y + max_y) / 2.0

    two_pi = 2.0 * math.pi
    theta = 0.0
    safety = 0
    placed_since = 0
    max_iter = rows * cols
    while frontier and safety < max_iter:
        safety += 1
        best = None
        best_key = None
        stale = []
        for (r, c) in frontier:
            if occ[r, c] != 0 or not adj_occupied(r, c):
                stale.append((r, c))
                continue
            x = ox + (c + 0.5) * cell
            y = oy + (r + 0.5) * cell
            dist = math.hypot(x - sx, y - sy)
            if mode == "beam":
                # Beam sweep: fill the closest empty spot to the seed. Ties -> any.
                key = (dist, 0.0)
                ang = 0.0
            else:
                ang = math.atan2(y - sy, x - sx)
                key = ((ang - theta) % two_pi, dist)
            if best_key is None or key < best_key:
                best_key = key
                best = (r, c, ang)
        for s in stale:
            frontier.discard(s)
        if best is None:
            break
        r, c, ang = best
        frontier.discard((r, c))
        if mode != "beam":
            theta = ang
        blk = place_beam5(r, c) if mode == "beam" else place_best(r, c)
        if blk is not None:
            add_frontier(*blk)
            placed_since += 1
            if mode == "beam" and placed_since >= 10:
                recent = placements[-placed_since:]
                compact(
                    min(p["_r0"] for p in recent) - min_gap,
                    max(p["_r1"] for p in recent) + min_gap,
                    min(p["_c0"] for p in recent) - min_gap,
                    max(p["_c1"] for p in recent) + min_gap,
                )
                placed_since = 0

    if mode == "beam":
        compact()  # final full-grid pass

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
    # For cut stones only the inside portion counts toward coverage.
    placed_area = sum(
        p["w_cm"] * p["h_cm"] * (p["cut"].get("inside_frac", 1.0) if p.get("cut") else 1.0)
        for p in placements
    )
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
