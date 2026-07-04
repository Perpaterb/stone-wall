import cv2
import numpy as np
import pytest

from app.cv.pipeline import CataloguerError, process_photo


def _synthetic(stones, span_x=100, span_y=80, with_markers=True):
    ppc = 8
    w, h = span_x * ppc + 200, span_y * ppc + 200
    img = np.full((h, w, 3), 40, np.uint8)
    corners = {
        0: (100, 100),
        1: (100 + span_x * ppc, 100),
        2: (100 + span_x * ppc, 100 + span_y * ppc),
        3: (100, 100 + span_y * ppc),
    }
    if with_markers:
        d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        for mid, (cx, cy) in corners.items():
            m = cv2.cvtColor(cv2.aruco.generateImageMarker(d, mid, 120), cv2.COLOR_GRAY2BGR)
            img[cy - 60 : cy + 60, cx - 60 : cx + 60] = m
    for cx, cy, sw, sh in stones:
        x = 100 + int((cx - sw / 2) * ppc)
        y = 100 + int((cy - sh / 2) * ppc)
        cv2.rectangle(img, (x, y), (x + int(sw * ppc), y + int(sh * ppc)), (200, 200, 200), -1)
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes()


def test_measures_known_stones():
    img = _synthetic([(30, 25, 30, 13), (70, 25, 20, 20), (40, 55, 36, 11)])
    res = process_photo(img, 100, 80)
    dims = sorted((c["width_cm"], c["height_cm"]) for c in res["candidates"])
    assert dims == [(20.0, 20.0), (30.0, 13.0), (36.0, 11.0)]
    for c in res["candidates"]:
        assert len(c["crop_png"]) > 0


def test_missing_markers_raises():
    img = _synthetic([(50, 40, 20, 20)], with_markers=False)
    with pytest.raises(CataloguerError):
        process_photo(img, 100, 80)


def test_no_stones_returns_empty():
    img = _synthetic([])
    res = process_photo(img, 100, 80)
    assert res["candidates"] == []


def test_bad_image_raises():
    with pytest.raises(CataloguerError):
        process_photo(b"not an image", 100, 80)
