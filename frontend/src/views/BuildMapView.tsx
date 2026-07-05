import Konva from "konva";
import { useEffect, useMemo, useRef, useState } from "react";
import { Circle, Layer, Line, Stage, Text } from "react-konva";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  createBuildMap,
  cropUrl,
  getBuildMap,
  getPlan,
  markUsed,
  type BuildMapDetail,
  type Placement,
} from "../api/client";

function placedPoly(p: Placement): number[] {
  const src =
    p.polygon && p.polygon.length >= 3
      ? p.polygon
      : [[0, 0], [p.w_cm, 0], [p.w_cm, p.h_cm], [0, p.h_cm]];
  const pts: number[] = [];
  for (const [px, py] of src) {
    if (p.rotation_deg === 90) pts.push(p.x_cm + py, p.y_cm + p.h_cm - px);
    else pts.push(p.x_cm + px, p.y_cm + py);
  }
  return pts;
}

export default function BuildMapView() {
  const { buildMapId } = useParams();
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<Konva.Stage>(null);
  const fittedRef = useRef(false);

  const [bm, setBm] = useState<BuildMapDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [size, setSize] = useState({ width: 800, height: 600 });
  const [scale, setScale] = useState(0.5);
  const [pos, setPos] = useState({ x: 40, y: 40 });
  const [copied, setCopied] = useState(false);
  const [selectedStone, setSelectedStone] = useState<string | null>(null);
  const [markMode, setMarkMode] = useState(false);
  const [busy, setBusy] = useState(false);
  const [showWall, setShowWall] = useState(true);
  const [showSeeds, setShowSeeds] = useState(false);
  const [planFallback, setPlanFallback] = useState<{ walls: number[][][]; negs: number[][][] }>({ walls: [], negs: [] });

  useEffect(() => {
    if (!buildMapId) return;
    getBuildMap(buildMapId).then(setBm).catch((e) => setError(String(e)));
  }, [buildMapId]);

  // Gentle poll so a crew sees each other's "used" marks.
  useEffect(() => {
    if (!buildMapId) return;
    const t = setInterval(() => {
      getBuildMap(buildMapId).then(setBm).catch(() => {});
    }, 10000);
    return () => clearInterval(t);
  }, [buildMapId]);

  useEffect(() => {
    function measure() {
      const el = containerRef.current;
      if (!el) return;
      setSize({ width: el.clientWidth, height: el.clientHeight });
    }
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  // Prefer the wall snapshot stored on the build map; fall back to the current
  // plan for older maps that predate the snapshot.
  useEffect(() => {
    if (!bm) return;
    const snap = (bm.params?.walls as number[][][]) ?? [];
    if (snap.length) return;
    getPlan(bm.project_id)
      .then((p) =>
        setPlanFallback({
          walls: p.shapes.filter((s) => s.kind === "wall").map((s) => s.polygon),
          negs: p.shapes.filter((s) => s.kind === "negative").map((s) => s.polygon),
        })
      )
      .catch(() => {});
  }, [bm]);

  const snapWalls = (bm?.params?.walls as number[][][]) ?? [];
  const snapNegs = (bm?.params?.negatives as number[][][]) ?? [];
  const walls = snapWalls.length ? snapWalls : planFallback.walls;
  const negs = snapNegs.length ? snapNegs : planFallback.negs;
  const seedPoints = (bm?.params?.seed_points as number[][]) ?? [];

  const bounds = useMemo(() => {
    if (!bm) return null;
    const wpolys = walls;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const poly of wpolys) {
      for (const [x, y] of poly) {
        minX = Math.min(minX, x); minY = Math.min(minY, y);
        maxX = Math.max(maxX, x); maxY = Math.max(maxY, y);
      }
    }
    for (const p of bm.placements) {
      minX = Math.min(minX, p.x_cm); minY = Math.min(minY, p.y_cm);
      maxX = Math.max(maxX, p.x_cm + p.w_cm); maxY = Math.max(maxY, p.y_cm + p.h_cm);
    }
    if (minX === Infinity) return null;
    return { minX, minY, maxX, maxY };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bm, planFallback]);

  useEffect(() => {
    if (fittedRef.current || !bounds || size.width < 50) return;
    const w = bounds.maxX - bounds.minX || 1;
    const h = bounds.maxY - bounds.minY || 1;
    const k = Math.min(size.width / w, size.height / h) * 0.85;
    setScale(k);
    setPos({
      x: (size.width - w * k) / 2 - bounds.minX * k,
      y: (size.height - h * k) / 2 - bounds.minY * k,
    });
    fittedRef.current = true;
  }, [bounds, size]);

  function handleWheel(e: Konva.KonvaEventObject<WheelEvent>) {
    e.evt.preventDefault();
    const ptr = stageRef.current?.getPointerPosition();
    if (!ptr) return;
    const before = [(ptr.x - pos.x) / scale, (ptr.y - pos.y) / scale];
    const factor = e.evt.deltaY < 0 ? 1.1 : 1 / 1.1;
    const ns = Math.max(0.02, Math.min(8, scale * factor));
    setScale(ns);
    setPos({ x: ptr.x - before[0] * ns, y: ptr.y - before[1] * ns });
  }

  function zoomBy(factor: number) {
    const cx = size.width / 2;
    const cy = size.height / 2;
    const before = [(cx - pos.x) / scale, (cy - pos.y) / scale];
    const ns = Math.max(0.02, Math.min(8, scale * factor));
    setScale(ns);
    setPos({ x: cx - before[0] * ns, y: cy - before[1] * ns });
  }

  const shareUrl = bm
    ? `${window.location.origin}${window.location.pathname}#/build/${bm.id}?k=${bm.share_key}`
    : "";

  async function copyShare() {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  async function toggleUsed(p: Placement) {
    if (!bm) return;
    setBusy(true);
    try {
      const used = p.status !== "used";
      const r = await markUsed(bm.id, p.stone_id, used);
      setBm((cur) =>
        cur
          ? {
              ...cur,
              placements: cur.placements.map((x) =>
                x.stone_id === p.stone_id ? { ...x, status: r.status } : x
              ),
            }
          : cur
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function regenerate() {
    if (!bm) return;
    setBusy(true);
    try {
      const seed = Math.floor(1 + Math.random() * 100000);
      const nextMethod = (bm.params?.method as string) || "spiral";
      const nextSeeds = (bm.params?.seeds as number) || 1;
      const next = await createBuildMap(bm.project_id, { seed, method: nextMethod, seeds: nextSeeds });
      fittedRef.current = false;
      navigate(`/build/${next.id}`);
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  }

  const showLabels = scale > 0.35;
  const r = bm?.report ?? null;
  const selected = bm?.placements.find((p) => p.stone_id === selectedStone) ?? null;
  const groutMin = bm?.params?.grout_min_cm as number | undefined;
  const groutMax = bm?.params?.grout_max_cm as number | undefined;

  function fillFor(p: Placement): string {
    if (p.status === "used") return "#c8c8c8";
    if (p.cut) return "#f0c9b0";
    return p.course_index % 2 === 0 ? "#e8d9b8" : "#e0cfa8";
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", fontFamily: "system-ui, sans-serif" }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", padding: 8, borderBottom: "1px solid #ddd", flexWrap: "wrap" }}>
        <Link to="/">&larr; Projects</Link>
        {bm && <Link to={`/projects/${bm.project_id}/plan`}>Plan</Link>}
        <strong>{bm?.name ?? "Build map"}</strong>
        {bm && <span style={{ color: "#888" }}>seed {bm.seed}</span>}
        <span style={{ flex: 1 }} />
        <button onClick={() => setShowWall((v) => !v)} style={{ fontWeight: showWall ? 700 : 400, background: showWall ? "#eef" : "#fff" }}>
          Wall
        </button>
        <button onClick={() => setShowSeeds((v) => !v)} style={{ fontWeight: showSeeds ? 700 : 400, background: showSeeds ? "#fde8e8" : "#fff" }}>
          Seeds
        </button>
        <button
          onClick={() => setMarkMode((m) => !m)}
          style={{ fontWeight: markMode ? 700 : 400, background: markMode ? "#d9f2d9" : "#fff" }}
        >
          {markMode ? "Mark mode: ON (tap to mark used)" : "Mark mode: off"}
        </button>
        <button onClick={regenerate} disabled={busy || !bm}>Regenerate</button>
        <button onClick={() => zoomBy(1.2)}>+</button>
        <button onClick={() => zoomBy(1 / 1.2)}>&minus;</button>
      </div>

      {error && <div style={{ padding: 8, color: "crimson" }}>{error}</div>}

      <div ref={containerRef} style={{ flex: 1, position: "relative", overflow: "hidden", background: "#f4f4f2" }}>
        <Stage
          ref={stageRef}
          width={size.width}
          height={size.height}
          scaleX={scale}
          scaleY={scale}
          x={pos.x}
          y={pos.y}
          draggable
          onWheel={handleWheel}
          onDragEnd={(e) => {
            if (e.target === e.target.getStage()) setPos({ x: e.target.x(), y: e.target.y() });
          }}
        >
          {showWall && (
            <Layer listening={false}>
              {walls.map((poly, i) => (
                <Line key={`w${i}`} points={poly.flat()} closed fill="#d9d5cc" stroke="#6b6252" strokeWidth={2 / scale} />
              ))}
              {negs.map((poly, i) => (
                <Line key={`n${i}`} points={poly.flat()} closed fill="#f4f4f2" stroke="#999" strokeWidth={1.5 / scale} dash={[6 / scale, 4 / scale]} />
              ))}
            </Layer>
          )}
          <Layer>
            {bm?.placements.map((p) => (
              <Line
                key={p.stone_id}
                points={placedPoly(p)}
                closed
                fill={fillFor(p)}
                opacity={p.status === "used" ? 0.55 : 1}
                stroke={p.stone_id === selectedStone ? "#2b6cb0" : p.cut ? "#c0392b" : "#8a7a52"}
                strokeWidth={(p.stone_id === selectedStone ? 2.4 : p.cut ? 1.6 : 0.8) / scale}
                hitStrokeWidth={6 / scale}
                onClick={() => (markMode ? toggleUsed(p) : setSelectedStone(p.stone_id))}
                onTap={() => (markMode ? toggleUsed(p) : setSelectedStone(p.stone_id))}
              />
            ))}
            {showLabels &&
              bm?.placements.map((p) => (
                <Text
                  key={`t${p.stone_id}`}
                  x={p.x_cm}
                  y={p.y_cm + p.h_cm / 2 - Math.min(p.w_cm, p.h_cm) * 0.18}
                  width={p.w_cm}
                  align="center"
                  text={p.code}
                  fontSize={Math.min(p.w_cm, p.h_cm) * 0.36}
                  fill="#5a4a2a"
                  listening={false}
                />
              ))}
          </Layer>
          {showSeeds && (
            <Layer listening={false}>
              {seedPoints.map((p, i) => (
                <Circle key={`seed${i}`} x={p[0]} y={p[1]} radius={9 / scale} fill="#e53e3e" stroke="#fff" strokeWidth={2 / scale} />
              ))}
              {seedPoints.map((p, i) => (
                <Text
                  key={`seedt${i}`}
                  x={p[0] - 20}
                  y={p[1] + 10 / scale}
                  width={40}
                  align="center"
                  text={`seed ${i + 1}`}
                  fontSize={13 / scale}
                  fill="#c0392b"
                  listening={false}
                />
              ))}
            </Layer>
          )}
        </Stage>

        {r && (
          <div style={{ position: "absolute", left: 12, bottom: 12, background: "rgba(255,255,255,0.96)", border: "1px solid #ddd", borderRadius: 8, padding: "10px 12px", fontSize: 13, minWidth: 190 }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Report</div>
            <div>Coverage: <strong>{r.coverage_pct}%</strong></div>
            <div>Stones used: {r.stones_used} / {r.stones_available}</div>
            <div>Courses: {r.courses}</div>
            <div>Cuts: {r.cut_count} ({r.cut_total_cm} cm)</div>
            <div>Gaps: {r.gap_count} ({r.gap_total_cm} cm)</div>
          </div>
        )}

        {bm && (
          <div style={{ position: "absolute", right: 12, top: 12, background: "rgba(255,255,255,0.96)", border: "1px solid #ddd", borderRadius: 8, padding: "10px 12px", fontSize: 12, width: 260 }}>
            {selected ? (
              <>
                <div style={{ fontWeight: 700, marginBottom: 4 }}>{selected.code}</div>
                {cropUrl(selected) && (
                  <img src={cropUrl(selected)!} alt="" style={{ width: "100%", maxHeight: 130, objectFit: "contain", background: "#faf8f2" }} />
                )}
                <div style={{ marginTop: 6 }}>
                  {selected.w_cm} x {selected.h_cm} cm
                  {selected.rotation_deg === 90 ? " (on end)" : ""}
                </div>
                {groutMin != null && groutMax != null && (
                  <div style={{ color: "#666" }}>grout each edge: {groutMin}-{groutMax} cm</div>
                )}
                {selected.cut ? (
                  <div style={{ color: "#c0392b" }}>
                    cut off {(selected.cut.removed_cm as number) ?? "?"} cm from the {(selected.cut.from as string) ?? "edge"}
                  </div>
                ) : (
                  <div style={{ color: "#2f855a" }}>no cut needed</div>
                )}
                <div style={{ marginTop: 6 }}>
                  status: <strong>{selected.status}</strong>
                </div>
                <button style={{ marginTop: 6, width: "100%", fontWeight: 700 }} disabled={busy} onClick={() => toggleUsed(selected)}>
                  {selected.status === "used" ? "Unmark used" : "Mark used"}
                </button>
              </>
            ) : (
              <div style={{ color: "#888" }}>Tap a stone to see details and mark it used.</div>
            )}
            <div style={{ marginTop: 10, borderTop: "1px solid #eee", paddingTop: 8 }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>Share link</div>
              <input readOnly value={shareUrl} style={{ width: "100%", fontSize: 11 }} onFocus={(e) => e.target.select()} />
              <button style={{ marginTop: 6 }} onClick={copyShare}>{copied ? "Copied" : "Copy link"}</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
