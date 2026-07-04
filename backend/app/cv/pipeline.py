"""Cataloguer computer-vision pipeline.

Detect the four ArUco markers, un-warp the photo to a true top-down cm-space,
segment the stones, measure each in centimetres, and crop an upright thumbnail.

Marker layout convention (ids from the printed sheet, DICT_4X4_50):
    id 0 = top-left, id 1 = top-right, id 2 = bottom-right, id 3 = bottom-left.
The physical span between marker centres (span_x_cm x span_y_cm) is the operator's
calibration.
"""

import cv2
import numpy as np

_ARUCO = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
_MARKER_IDS = [0, 1, 2, 3]


class CataloguerError(Exception):
    pass


def _detect_markers(gray: np.ndarray) -> dict:
    detector = cv2.aruco.ArucoDetector(_ARUCO, cv2.aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(gray)
    found = {}
    if ids is not None:
        for c, i in zip(corners, ids.flatten()):
            pts = c.reshape(4, 2).astype(np.float32)
            found[int(i)] = {"center": pts.mean(axis=0), "corners": pts}
    return found


def _crop_rotated(img: np.ndarray, rect) -> np.ndarray:
    (cx, cy), (w, h), angle = rect
    if w < h:
        angle += 90.0
        w, h = h, w
    m = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    rotated = cv2.warpAffine(img, m, (img.shape[1], img.shape[0]))
    x = int(round(cx - w / 2))
    y = int(round(cy - h / 2))
    x, y = max(0, x), max(0, y)
    crop = rotated[y : y + int(round(h)), x : x + int(round(w))]
    return crop


def process_photo(
    image_bytes: bytes,
    span_x_cm: float,
    span_y_cm: float,
    px_per_cm: float = 4.0,
    min_side_cm: float = 8.0,
    max_side_cm: float = 45.0,
) -> dict:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise CataloguerError("Could not decode image")

    # Cap resolution for stable, fast detection.
    max_dim = max(img.shape[:2])
    if max_dim > 2500:
        s = 2500 / max_dim
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    markers = _detect_markers(gray)
    missing = [i for i in _MARKER_IDS if i not in markers]
    if missing:
        raise CataloguerError(
            f"Found {4 - len(missing)}/4 markers (missing ids {missing}). Retake the photo."
        )

    # Mask the markers with the image median so they do not segment as stones.
    med = np.median(img.reshape(-1, 3), axis=0)
    for i in _MARKER_IDS:
        cv2.fillConvexPoly(img, markers[i]["corners"].astype(np.int32), med.tolist())

    ppc = float(px_per_cm)
    src = np.array([markers[i]["center"] for i in _MARKER_IDS], dtype=np.float32)
    dst = np.array(
        [
            [0.0, 0.0],
            [span_x_cm * ppc, 0.0],
            [span_x_cm * ppc, span_y_cm * ppc],
            [0.0, span_y_cm * ppc],
        ],
        dtype=np.float32,
    )
    hmat = cv2.getPerspectiveTransform(src, dst)
    out_w = int(round(span_x_cm * ppc))
    out_h = int(round(span_y_cm * ppc))
    warped = cv2.warpPerspective(img, hmat, (out_w, out_h))
    warped_gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

    # Pale stones on a dark sheet: Otsu, foreground bright.
    _, th = cv2.threshold(warped_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = np.ones((3, 3), np.uint8)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel, iterations=2)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for c in contours:
        rect = cv2.minAreaRect(c)
        (cx, cy), (rw, rh), angle = rect
        long_cm = max(rw, rh) / ppc
        short_cm = min(rw, rh) / ppc
        if long_cm < min_side_cm or long_cm > max_side_cm:
            continue
        if short_cm < min_side_cm * 0.5 or short_cm > max_side_cm:
            continue

        area_cm2 = cv2.contourArea(c) / (ppc * ppc)
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True).reshape(-1, 2).astype(float)
        minx, miny = approx.min(axis=0)
        poly_local = [
            [round((px - minx) / ppc, 2), round((py - miny) / ppc, 2)] for px, py in approx
        ]

        crop = _crop_rotated(warped, rect)
        if crop.size == 0:
            continue
        ok, buf = cv2.imencode(".png", crop)
        if not ok:
            continue

        candidates.append(
            {
                "width_cm": round(long_cm, 1),
                "height_cm": round(short_cm, 1),
                "angle_deg": round(float(angle), 1),
                "area_cm2": round(float(area_cm2), 1),
                "polygon": poly_local,
                "sheet_x_cm": round(cx / ppc, 1),
                "sheet_y_cm": round(cy / ppc, 1),
                "crop_png": buf.tobytes(),
                "_cy_px": cy,
                "_cx_px": cx,
                "_h_px": min(rw, rh),
            }
        )

    # Reading order: left-to-right within rough rows, top-to-bottom.
    if candidates:
        band = float(np.median([c["_h_px"] for c in candidates])) * 0.7 or 1.0
        candidates.sort(key=lambda c: (int(c["_cy_px"] // band), c["_cx_px"]))
    for c in candidates:
        del c["_cy_px"], c["_cx_px"], c["_h_px"]

    ok, wbuf = cv2.imencode(".jpg", warped, [cv2.IMWRITE_JPEG_QUALITY, 85])
    warped_jpg = wbuf.tobytes() if ok else b""

    return {
        "px_per_cm": ppc,
        "warped_jpg": warped_jpg,
        "candidates": candidates,
    }
