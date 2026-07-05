import Konva from "konva";
import { useEffect, useMemo, useRef, useState } from "react";
import { Circle, Layer, Line, Stage, Text } from "react-konva";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  clearStones,
  createBuildMap,
  deleteBuildMap,
  generateDummyStones,
  getCoverage,
  getPlan,
  getProject,
  listBuildMaps,
  putPlan,
  updateProject,
  type BuildMapSummary,
  type Coverage,
  type Project,
} from "../api/client";
import { orthoSnap, polygonAreaCm2 } from "../geometry";

type Tool = "pan" | "wall" | "negative" | "edit";

interface EditShape {
  id: string;
  kind: "wall" | "negative";
  polygon: number[][];
}

let tmpCounter = 0;
const newId = () => `tmp-${tmpCounter++}`;

export default function PlanView() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<Konva.Stage>(null);
  const fittedRef = useRef(false);

  const [project, setProject] = useState<Project | null>(null);
  const [shapes, setShapes] = useState<EditShape[]>([]);
  const [draft, setDraft] = useState<number[][]>([]);
  const [tool, setTool] = useState<Tool>("pan");
  const [ortho, setOrtho] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [size, setSize] = useState({ width: 800, height: 600 });
  const [scale, setScale] = useState(0.5);
  const [pos, setPos] = useState({ x: 40, y: 40 });
  const [status, setStatus] = useState<string | null>(null);
  const [serverCoverage, setServerCoverage] = useState<Coverage | null>(null);
  const [buildMaps, setBuildMaps] = useState<BuildMapSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [method, setMethod] = useState("spiral");

  function refreshCoverage() {
    if (!projectId) return;
    getCoverage(projectId).then(setServerCoverage).catch(() => {});
  }
  function refreshBuildMaps() {
    if (!projectId) return;
    listBuildMaps(projectId).then(setBuildMaps).catch(() => {});
  }

  useEffect(() => {
    if (!projectId) return;
    getProject(projectId).then(setProject).catch((e) => setStatus(String(e)));
    getPlan(projectId)
      .then((p) =>
        setShapes(
          p.shapes.map((s) => ({ id: s.id ?? newId(), kind: s.kind, polygon: s.polygon }))
        )
      )
      .catch((e) => setStatus(String(e)));
    refreshCoverage();
    refreshBuildMaps();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function genStones() {
    if (!projectId) return;
    setBusy(true);
    setStatus("Generating stones...");
    try {
      const r = await generateDummyStones(projectId, { count: 300, seed: 1 });
      setStatus(`${r.total} stones in catalogue`);
      refreshCoverage();
    } catch (e) {
      setStatus(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function clearStonesFn() {
    if (!projectId) return;
    setBusy(true);
    try {
      await clearStones(projectId);
      setStatus("Stones cleared");
      refreshCoverage();
    } catch (e) {
      setStatus(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function genBuildMap() {
    if (!projectId) return;
    setBusy(true);
    setStatus("Solving layout...");
    try {
      // Save the current plan first so the solver sees the latest walls.
      await putPlan(
        projectId,
        shapes.map((s, i) => ({ kind: s.kind, polygon: s.polygon, z_order: i }))
      );
      const seed = Math.floor(1 + Math.random() * 100000);
      const bm = await createBuildMap(projectId, { seed, method });
      navigate(`/build/${bm.id}`);
    } catch (e) {
      setStatus(String(e));
      setBusy(false);
    }
  }

  async function delBuildMap(id: string) {
    setBusy(true);
    try {
      await deleteBuildMap(id);
      refreshBuildMaps();
    } catch (e) {
      setStatus(String(e));
    } finally {
      setBusy(false);
    }
  }

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

  // Fit a ~1300 x 400 cm working area into the viewport once.
  useEffect(() => {
    if (fittedRef.current || size.width < 50) return;
    const k = Math.min(size.width / 1300, size.height / 400) * 0.9;
    setScale(k);
    setPos({ x: 30, y: 30 });
    fittedRef.current = true;
  }, [size]);

  function toWorld(px: number, py: number): number[] {
    return [(px - pos.x) / scale, (py - pos.y) / scale];
  }

  function handleStageClick(e: Konva.KonvaEventObject<MouseEvent>) {
    if (tool !== "wall" && tool !== "negative") {
      if (tool === "edit" && e.target === e.target.getStage()) setSelectedId(null);
      return;
    }
    const stage = stageRef.current;
    const ptr = stage?.getPointerPosition();
    if (!ptr) return;
    let world = toWorld(ptr.x, ptr.y);
    if (ortho && draft.length > 0) world = orthoSnap(draft[draft.length - 1], world);
    setDraft((d) => [...d, world]);
  }

  function finishDraft() {
    if (draft.length >= 3 && (tool === "wall" || tool === "negative")) {
      setShapes((s) => [...s, { id: newId(), kind: tool, polygon: draft }]);
    }
    setDraft([]);
  }

  function handleWheel(e: Konva.KonvaEventObject<WheelEvent>) {
    e.evt.preventDefault();
    const ptr = stageRef.current?.getPointerPosition();
    if (!ptr) return;
    const worldBefore = [(ptr.x - pos.x) / scale, (ptr.y - pos.y) / scale];
    const factor = e.evt.deltaY < 0 ? 1.1 : 1 / 1.1;
    const newScale = Math.max(0.02, Math.min(5, scale * factor));
    setScale(newScale);
    setPos({ x: ptr.x - worldBefore[0] * newScale, y: ptr.y - worldBefore[1] * newScale });
  }

  function zoomBy(factor: number) {
    const cx = size.width / 2;
    const cy = size.height / 2;
    const worldBefore = [(cx - pos.x) / scale, (cy - pos.y) / scale];
    const newScale = Math.max(0.02, Math.min(5, scale * factor));
    setScale(newScale);
    setPos({ x: cx - worldBefore[0] * newScale, y: cy - worldBefore[1] * newScale });
  }

  function updateVertex(shapeId: string, idx: number, world: number[]) {
    setShapes((s) =>
      s.map((sh) =>
        sh.id === shapeId
          ? { ...sh, polygon: sh.polygon.map((p, i) => (i === idx ? world : p)) }
          : sh
      )
    );
  }

  function deleteSelected() {
    if (!selectedId) return;
    setShapes((s) => s.filter((sh) => sh.id !== selectedId));
    setSelectedId(null);
  }

  function deleteShapeById(id: string) {
    setShapes((s) => s.filter((sh) => sh.id !== id));
    setSelectedId((cur) => (cur === id ? null : cur));
  }

  function setVertexXY(id: string, i: number, x: number, y: number) {
    if (Number.isNaN(x) || Number.isNaN(y)) return;
    setShapes((s) =>
      s.map((sh) =>
        sh.id === id ? { ...sh, polygon: sh.polygon.map((p, k) => (k === i ? [x, y] : p)) } : sh
      )
    );
  }

  // Set an edge's length by moving its end vertex along the edge direction.
  function setEdgeLength(id: string, i: number, newLen: number) {
    if (Number.isNaN(newLen) || newLen <= 0) return;
    setShapes((s) =>
      s.map((sh) => {
        if (sh.id !== id) return sh;
        const n = sh.polygon.length;
        const a = sh.polygon[i];
        const b = sh.polygon[(i + 1) % n];
        const dx = b[0] - a[0];
        const dy = b[1] - a[1];
        const cur = Math.hypot(dx, dy) || 1;
        const nb = [a[0] + (dx / cur) * newLen, a[1] + (dy / cur) * newLen];
        return { ...sh, polygon: sh.polygon.map((p, k) => (k === (i + 1) % n ? nb : p)) };
      })
    );
  }

  // Set the interior angle at a vertex by rotating its outgoing edge.
  function setVertexAngleDeg(id: string, i: number, deg: number) {
    if (Number.isNaN(deg)) return;
    setShapes((s) =>
      s.map((sh) => {
        if (sh.id !== id) return sh;
        const n = sh.polygon.length;
        const prev = sh.polygon[(i - 1 + n) % n];
        const v = sh.polygon[i];
        const next = sh.polygon[(i + 1) % n];
        const inAng = Math.atan2(prev[1] - v[1], prev[0] - v[0]);
        const curOut = Math.atan2(next[1] - v[1], next[0] - v[0]);
        const outLen = Math.hypot(next[0] - v[0], next[1] - v[1]);
        const sign = Math.sin(curOut - inAng) >= 0 ? 1 : -1;
        const newOut = inAng + sign * (deg * Math.PI) / 180;
        const nn = [v[0] + Math.cos(newOut) * outLen, v[1] + Math.sin(newOut) * outLen];
        return { ...sh, polygon: sh.polygon.map((p, k) => (k === (i + 1) % n ? nn : p)) };
      })
    );
  }

  function edgeLen(poly: number[][], i: number) {
    const a = poly[i];
    const b = poly[(i + 1) % poly.length];
    return Math.hypot(b[0] - a[0], b[1] - a[1]);
  }

  function vertexAngleDeg(poly: number[][], i: number) {
    const n = poly.length;
    const prev = poly[(i - 1 + n) % n];
    const v = poly[i];
    const next = poly[(i + 1) % n];
    const a1 = Math.atan2(prev[1] - v[1], prev[0] - v[0]);
    const a2 = Math.atan2(next[1] - v[1], next[0] - v[0]);
    let d = (Math.abs(a1 - a2) * 180) / Math.PI;
    if (d > 180) d = 360 - d;
    return d;
  }

  async function save() {
    if (!projectId) return;
    setStatus("Saving...");
    try {
      await putPlan(
        projectId,
        shapes.map((s, i) => ({ kind: s.kind, polygon: s.polygon, z_order: i }))
      );
      setStatus("Saved");
    } catch (e) {
      setStatus(String(e));
    }
  }

  async function saveGrout(min: number, max: number) {
    if (!projectId || Number.isNaN(min) || Number.isNaN(max)) return;
    try {
      setProject(await updateProject(projectId, { grout_min_cm: min, grout_max_cm: max }));
    } catch (e) {
      setStatus(String(e));
    }
  }

  const coverage = useMemo(() => {
    let wall = 0;
    let neg = 0;
    for (const s of shapes) {
      const a = polygonAreaCm2(s.polygon);
      if (s.kind === "wall") wall += a;
      else neg += a;
    }
    return { wall, neg, net: Math.max(0, wall - neg) };
  }, [shapes]);

  const fillFor = (kind: string, selected: boolean) =>
    kind === "wall"
      ? selected
        ? "rgba(70,130,220,0.45)"
        : "rgba(70,130,220,0.3)"
      : selected
        ? "rgba(220,80,80,0.45)"
        : "rgba(220,80,80,0.3)";

  const grid = useMemo(() => {
    const lines: number[][] = [];
    for (let x = 0; x <= 1400; x += 100) lines.push([x, 0, x, 500]);
    for (let y = 0; y <= 500; y += 100) lines.push([0, y, 1400, y]);
    return lines;
  }, []);

  const btn = (active: boolean) => ({
    padding: "6px 10px",
    fontWeight: active ? 700 : 400,
    background: active ? "#eef" : "#fff",
    border: "1px solid #ccc",
    borderRadius: 4,
    cursor: "pointer",
  });

  const selShape = shapes.find((s) => s.id === selectedId) ?? null;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", fontFamily: "system-ui, sans-serif" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", padding: 8, borderBottom: "1px solid #ddd", flexWrap: "wrap" }}>
        <Link to="/">&larr; Projects</Link>
        <strong>{project?.name ?? "..."}</strong>
        {projectId && <Link to={`/projects/${projectId}/stones`}>Catalogue</Link>}
        {projectId && <Link to={`/projects/${projectId}/add-stones`}>Add stones</Link>}
        <span style={{ width: 8 }} />
        {(["pan", "wall", "negative", "edit"] as Tool[]).map((t) => (
          <button
            key={t}
            style={btn(tool === t)}
            onClick={() => {
              setTool(t);
              setDraft([]);
              setSelectedId(null);
            }}
          >
            {t}
          </button>
        ))}
        <label style={{ marginLeft: 4 }}>
          <input type="checkbox" checked={ortho} onChange={(e) => setOrtho(e.target.checked)} /> ortho
        </label>
        {(tool === "wall" || tool === "negative") && (
          <>
            <button style={btn(false)} onClick={finishDraft} disabled={draft.length < 3}>
              Finish shape
            </button>
            <button style={btn(false)} onClick={() => setDraft([])} disabled={draft.length === 0}>
              Cancel
            </button>
          </>
        )}
        {tool === "edit" && (
          <button style={btn(false)} onClick={deleteSelected} disabled={!selectedId}>
            Delete selected
          </button>
        )}
        <span style={{ flex: 1 }} />
        <button style={btn(false)} onClick={() => zoomBy(1.2)}>+</button>
        <button style={btn(false)} onClick={() => zoomBy(1 / 1.2)}>&minus;</button>
        <button style={{ ...btn(false), fontWeight: 700 }} onClick={save}>Save</button>
      </div>

      {project && (
        <div style={{ display: "flex", gap: 12, alignItems: "center", padding: "6px 8px", borderBottom: "1px solid #eee", fontSize: 14 }}>
          <span>Grout cm:</span>
          <label>
            min{" "}
            <input
              type="number"
              step="0.1"
              defaultValue={project.grout_min_cm}
              style={{ width: 60 }}
              onBlur={(e) => saveGrout(parseFloat(e.target.value), project.grout_max_cm)}
            />
          </label>
          <label>
            max{" "}
            <input
              type="number"
              step="0.1"
              defaultValue={project.grout_max_cm}
              style={{ width: 60 }}
              onBlur={(e) => saveGrout(project.grout_min_cm, parseFloat(e.target.value))}
            />
          </label>
          {status && <span style={{ color: "#888" }}>{status}</span>}
        </div>
      )}

      <div ref={containerRef} style={{ flex: 1, position: "relative", overflow: "hidden", background: "#fafafa" }}>
        <Stage
          ref={stageRef}
          width={size.width}
          height={size.height}
          scaleX={scale}
          scaleY={scale}
          x={pos.x}
          y={pos.y}
          draggable={tool === "pan"}
          onWheel={handleWheel}
          onClick={handleStageClick}
          onTap={handleStageClick as unknown as (e: Konva.KonvaEventObject<Event>) => void}
          onDragEnd={(e) => {
            if (e.target === e.target.getStage()) setPos({ x: e.target.x(), y: e.target.y() });
          }}
        >
          <Layer listening={false}>
            {grid.map((l, i) => (
              <Line key={i} points={l} stroke="#e6e6e6" strokeWidth={1 / scale} />
            ))}
          </Layer>
          <Layer>
            {shapes.map((s) => (
              <Line
                key={s.id}
                points={s.polygon.flat()}
                closed
                fill={fillFor(s.kind, s.id === selectedId)}
                stroke={s.kind === "wall" ? "#2b6cb0" : "#c53030"}
                strokeWidth={2 / scale}
                onClick={() => tool === "edit" && setSelectedId(s.id)}
                onTap={() => tool === "edit" && setSelectedId(s.id)}
              />
            ))}
            {draft.length > 0 && (
              <Line points={draft.flat()} stroke="#555" strokeWidth={2 / scale} dash={[6 / scale, 4 / scale]} />
            )}
            {draft.map((p, i) => (
              <Circle key={`d${i}`} x={p[0]} y={p[1]} radius={5 / scale} fill="#555" />
            ))}
            {/* Edit mode: every corner of every shape is a big draggable handle. */}
            {tool === "edit" &&
              shapes.map((s) =>
                s.polygon.map((p, i) => (
                  <Circle
                    key={`${s.id}-${i}`}
                    x={p[0]}
                    y={p[1]}
                    radius={10 / scale}
                    hitStrokeWidth={12 / scale}
                    fill={s.id === selectedId ? "#2b6cb0" : "#ffffff"}
                    stroke="#2b6cb0"
                    strokeWidth={2 / scale}
                    draggable
                    onMouseDown={() => setSelectedId(s.id)}
                    onTouchStart={() => setSelectedId(s.id)}
                    onDragStart={() => setSelectedId(s.id)}
                    onDragMove={(e) => updateVertex(s.id, i, [e.target.x(), e.target.y()])}
                  />
                ))
              )}
            {/* Edge length labels for the selected shape. */}
            {tool === "edit" &&
              selShape &&
              selShape.polygon.map((p, i) => {
                const q = selShape.polygon[(i + 1) % selShape.polygon.length];
                return (
                  <Text
                    key={`len-${i}`}
                    x={(p[0] + q[0]) / 2}
                    y={(p[1] + q[1]) / 2}
                    text={`${edgeLen(selShape.polygon, i).toFixed(0)}`}
                    fontSize={14 / scale}
                    fill="#1a1a1a"
                    listening={false}
                  />
                );
              })}
          </Layer>
        </Stage>

        {tool === "edit" && (
          <div style={{ position: "absolute", left: 12, top: 12, background: "rgba(255,255,255,0.97)", border: "1px solid #ddd", borderRadius: 8, padding: "10px 12px", fontSize: 12, width: 250, maxHeight: "70vh", overflowY: "auto" }}>
            <div style={{ fontWeight: 700, marginBottom: 6 }}>Shapes</div>
            {shapes.length === 0 && <div style={{ color: "#999" }}>Draw a wall first.</div>}
            {shapes.map((s, idx) => (
              <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                <button
                  style={{ ...btn(s.id === selectedId), flex: 1, textAlign: "left", padding: "3px 6px" }}
                  onClick={() => setSelectedId(s.id)}
                >
                  {s.kind} {idx + 1}
                </button>
                <button style={{ ...btn(false), padding: "3px 6px", color: "crimson" }} onClick={() => deleteShapeById(s.id)}>x</button>
              </div>
            ))}

            {selShape && (
              <div style={{ marginTop: 8, borderTop: "1px solid #eee", paddingTop: 6 }}>
                <div style={{ fontWeight: 700, marginBottom: 4 }}>Corners (cm)</div>
                {selShape.polygon.map((p, i) => (
                  <div key={`v${i}`} style={{ display: "flex", gap: 4, alignItems: "center", marginBottom: 3 }}>
                    <span style={{ width: 14, color: "#888" }}>{i + 1}</span>
                    <input type="number" value={Math.round(p[0])} style={{ width: 52 }}
                      onChange={(e) => setVertexXY(selShape.id, i, parseFloat(e.target.value), p[1])} />
                    <input type="number" value={Math.round(p[1])} style={{ width: 52 }}
                      onChange={(e) => setVertexXY(selShape.id, i, p[0], parseFloat(e.target.value))} />
                    <span style={{ color: "#888" }}>∠</span>
                    <input type="number" value={Math.round(vertexAngleDeg(selShape.polygon, i))} style={{ width: 46 }}
                      onChange={(e) => setVertexAngleDeg(selShape.id, i, parseFloat(e.target.value))} />
                  </div>
                ))}
                <div style={{ fontWeight: 700, margin: "6px 0 4px" }}>Edge lengths (cm)</div>
                {selShape.polygon.map((_, i) => (
                  <div key={`e${i}`} style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 3 }}>
                    <span style={{ width: 42, color: "#888" }}>{i + 1}&rarr;{((i + 1) % selShape.polygon.length) + 1}</span>
                    <input type="number" value={Math.round(edgeLen(selShape.polygon, i))} style={{ width: 70 }}
                      onChange={(e) => setEdgeLength(selShape.id, i, parseFloat(e.target.value))} />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div style={{ position: "absolute", left: 12, bottom: 12, background: "rgba(255,255,255,0.95)", border: "1px solid #ddd", borderRadius: 8, padding: "10px 12px", fontSize: 13, minWidth: 180 }}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>Coverage</div>
          <div>Wall area: {(coverage.wall / 10000).toFixed(2)} m&sup2;</div>
          <div>Negative: {(coverage.neg / 10000).toFixed(2)} m&sup2;</div>
          <div>Net wall: <strong>{(coverage.net / 10000).toFixed(2)} m&sup2;</strong></div>
          {serverCoverage && (
            <div style={{ marginTop: 4, borderTop: "1px solid #eee", paddingTop: 4 }}>
              <div>
                Stones: {serverCoverage.stone_count} avail,{" "}
                {(serverCoverage.stone_area_cm2 / 10000).toFixed(2)} m&sup2;
              </div>
              <div>
                Can cover:{" "}
                <strong>
                  {coverage.net > 0
                    ? Math.min(999, (serverCoverage.stone_area_cm2 / coverage.net) * 100).toFixed(0)
                    : 0}
                  %
                </strong>{" "}
                of wall
              </div>
            </div>
          )}
        </div>

        <div style={{ position: "absolute", right: 12, top: 12, background: "rgba(255,255,255,0.96)", border: "1px solid #ddd", borderRadius: 8, padding: "10px 12px", fontSize: 13, width: 210 }}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>Stones</div>
          <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
            <button style={btn(false)} onClick={genStones} disabled={busy}>+300 dummy</button>
            <button style={btn(false)} onClick={clearStonesFn} disabled={busy}>Clear</button>
          </div>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>Build maps</div>
          <label style={{ display: "block", marginBottom: 6 }}>
            style{" "}
            <select value={method} onChange={(e) => setMethod(e.target.value)}>
              <option value="spiral">spiral (rubble)</option>
              <option value="skyline">skyline (coursed)</option>
            </select>
          </label>
          <button style={{ ...btn(false), width: "100%", marginBottom: 8 }} onClick={genBuildMap} disabled={busy}>
            {busy ? "Solving..." : "Generate build map"}
          </button>
          <div style={{ maxHeight: 200, overflowY: "auto" }}>
            {buildMaps.length === 0 && <div style={{ color: "#999" }}>none yet</div>}
            {buildMaps.map((b) => (
              <div key={b.id} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                <Link to={`/build/${b.id}`} style={{ flex: 1 }}>
                  {b.report?.coverage_pct ?? "?"}% ({b.report?.stones_used ?? "?"})
                </Link>
                <button style={{ ...btn(false), padding: "2px 6px" }} onClick={() => delBuildMap(b.id)} disabled={busy}>
                  x
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
