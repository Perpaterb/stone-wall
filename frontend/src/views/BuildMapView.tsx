import Konva from "konva";
import { useEffect, useMemo, useRef, useState } from "react";
import { Layer, Rect, Stage, Text } from "react-konva";
import { Link, useParams } from "react-router-dom";

import { getBuildMap, type BuildMapDetail } from "../api/client";

export default function BuildMapView() {
  const { buildMapId } = useParams();
  const containerRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<Konva.Stage>(null);
  const fittedRef = useRef(false);

  const [bm, setBm] = useState<BuildMapDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [size, setSize] = useState({ width: 800, height: 600 });
  const [scale, setScale] = useState(0.5);
  const [pos, setPos] = useState({ x: 40, y: 40 });
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!buildMapId) return;
    getBuildMap(buildMapId).then(setBm).catch((e) => setError(String(e)));
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

  const bounds = useMemo(() => {
    if (!bm || bm.placements.length === 0) return null;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const p of bm.placements) {
      minX = Math.min(minX, p.x_cm);
      minY = Math.min(minY, p.y_cm);
      maxX = Math.max(maxX, p.x_cm + p.w_cm);
      maxY = Math.max(maxY, p.y_cm + p.h_cm);
    }
    return { minX, minY, maxX, maxY };
  }, [bm]);

  // Fit the wall into the viewport once placements + size are known.
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

  const showLabels = scale > 0.35;
  const r = bm?.report ?? null;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", fontFamily: "system-ui, sans-serif" }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", padding: 8, borderBottom: "1px solid #ddd", flexWrap: "wrap" }}>
        <Link to="/">&larr; Projects</Link>
        <strong>{bm?.name ?? "Build map"}</strong>
        {bm && <span style={{ color: "#888" }}>seed {bm.seed}</span>}
        <span style={{ flex: 1 }} />
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
          <Layer>
            {bm?.placements.map((p, i) => {
              const isCut = !!p.cut;
              const band = p.course_index % 2 === 0 ? "#e8d9b8" : "#e0cfa8";
              return (
                <Rect
                  key={i}
                  x={p.x_cm}
                  y={p.y_cm}
                  width={p.w_cm}
                  height={p.h_cm}
                  fill={isCut ? "#f0c9b0" : band}
                  stroke={isCut ? "#c0392b" : "#8a7a52"}
                  strokeWidth={(isCut ? 1.6 : 0.8) / scale}
                />
              );
            })}
            {showLabels &&
              bm?.placements.map((p, i) => (
                <Text
                  key={`t${i}`}
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
        </Stage>

        {r && (
          <div style={{ position: "absolute", left: 12, bottom: 12, background: "rgba(255,255,255,0.96)", border: "1px solid #ddd", borderRadius: 8, padding: "10px 12px", fontSize: 13, minWidth: 190 }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Report</div>
            <div>Coverage: <strong>{r.coverage_pct}%</strong></div>
            <div>Stones used: {r.stones_used} / {r.stones_available}</div>
            <div>Courses: {r.courses}</div>
            <div>Cuts: {r.cut_count} ({r.cut_total_cm} cm)</div>
            <div>Gaps: {r.gap_count} ({r.gap_total_cm} cm)</div>
            <div style={{ marginTop: 6, display: "flex", gap: 6, alignItems: "center" }}>
              <span style={{ width: 12, height: 12, background: "#f0c9b0", border: "1.5px solid #c0392b", display: "inline-block" }} />
              <span style={{ color: "#666" }}>needs a cut</span>
            </div>
          </div>
        )}

        {bm && (
          <div style={{ position: "absolute", right: 12, top: 12, background: "rgba(255,255,255,0.96)", border: "1px solid #ddd", borderRadius: 8, padding: "8px 10px", fontSize: 12, maxWidth: 320 }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Share link</div>
            <input readOnly value={shareUrl} style={{ width: "100%", fontSize: 11 }} onFocus={(e) => e.target.select()} />
            <button style={{ marginTop: 6 }} onClick={copyShare}>{copied ? "Copied" : "Copy link"}</button>
          </div>
        )}
      </div>
    </div>
  );
}
