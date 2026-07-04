import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { confirmStones, cropUrl, uploadPhoto, type PhotoResult, type Stone } from "../api/client";

interface Candidate extends Stone {
  keep: boolean;
}

export default function AddStonesView() {
  const { projectId } = useParams();
  const [spanX, setSpanX] = useState(100);
  const [spanY, setSpanY] = useState(100);
  const [storage, setStorage] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [minSide, setMinSide] = useState(8);
  const [maxSide, setMaxSide] = useState(45);
  const [thresholdMode, setThresholdMode] = useState("otsu");
  const [invert, setInvert] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [result, setResult] = useState<PhotoResult | null>(null);
  const [cands, setCands] = useState<Candidate[]>([]);

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !projectId) return;
    setBusy(true);
    setStatus("Detecting markers and measuring stones...");
    setResult(null);
    setCands([]);
    try {
      const r = await uploadPhoto(projectId, file, spanX, spanY, storage, {
        min_side_cm: minSide,
        max_side_cm: maxSide,
        threshold_mode: thresholdMode,
        invert,
      });
      setResult(r);
      setCands(r.stones.map((s) => ({ ...s, keep: true })));
      setStatus(`Detected ${r.detected} stones. Review, then confirm.`);
    } catch (err) {
      setStatus(String(err));
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  function move(i: number, dir: -1 | 1) {
    setCands((c) => {
      const j = i + dir;
      if (j < 0 || j >= c.length) return c;
      const next = [...c];
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });
  }

  function toggleKeep(id: string) {
    setCands((c) => c.map((s) => (s.id === id ? { ...s, keep: !s.keep } : s)));
  }

  async function confirm() {
    if (!projectId) return;
    setBusy(true);
    setStatus("Saving...");
    try {
      const ordered = cands.filter((s) => s.keep).map((s) => s.id);
      const deleted = cands.filter((s) => !s.keep).map((s) => s.id);
      const saved = await confirmStones(projectId, { ordered_ids: ordered, deleted_ids: deleted });
      setStatus(`Catalogued ${saved.length} stones (${saved[0]?.code ?? ""} onward). Add another photo or view the catalogue.`);
      setResult(null);
      setCands([]);
    } catch (err) {
      setStatus(String(err));
    } finally {
      setBusy(false);
    }
  }

  const keptCount = cands.filter((s) => s.keep).length;

  return (
    <main style={{ maxWidth: 900, margin: "1rem auto", padding: "0 1rem", fontFamily: "system-ui, sans-serif" }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <Link to="/">&larr; Projects</Link>
        {projectId && <Link to={`/projects/${projectId}/plan`}>Plan</Link>}
        {projectId && <Link to={`/projects/${projectId}/stones`}>Catalogue</Link>}
        <h2 style={{ margin: "0 0 0 8px" }}>Add stones</h2>
      </div>

      <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap", margin: "1rem 0", padding: 12, border: "1px solid #eee", borderRadius: 8 }}>
        <label>Marker span X (cm)<br /><input type="number" value={spanX} onChange={(e) => setSpanX(parseFloat(e.target.value))} style={{ width: 90 }} /></label>
        <label>Marker span Y (cm)<br /><input type="number" value={spanY} onChange={(e) => setSpanY(parseFloat(e.target.value))} style={{ width: 90 }} /></label>
        <label>Storage label<br /><input value={storage} onChange={(e) => setStorage(e.target.value)} placeholder="Pallet B" style={{ width: 140 }} /></label>
        <label>
          Photo<br />
          <input type="file" accept="image/*" capture="environment" onChange={onFile} disabled={busy} />
        </label>
        <button type="button" onClick={() => setAdvanced((a) => !a)}>{advanced ? "Hide" : "Tuning"}</button>
      </div>

      {advanced && (
        <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap", margin: "0 0 1rem", padding: 12, border: "1px dashed #ccc", borderRadius: 8, fontSize: 13 }}>
          <label>min side (cm)<br /><input type="number" value={minSide} onChange={(e) => setMinSide(parseFloat(e.target.value))} style={{ width: 70 }} /></label>
          <label>max side (cm)<br /><input type="number" value={maxSide} onChange={(e) => setMaxSide(parseFloat(e.target.value))} style={{ width: 70 }} /></label>
          <label>threshold<br />
            <select value={thresholdMode} onChange={(e) => setThresholdMode(e.target.value)}>
              <option value="otsu">otsu (even light)</option>
              <option value="adaptive">adaptive (uneven light)</option>
            </select>
          </label>
          <label><input type="checkbox" checked={invert} onChange={(e) => setInvert(e.target.checked)} /> invert (dark stones)</label>
        </div>
      )}

      {status && <p style={{ color: status.startsWith("Error") || status.includes("failed") ? "crimson" : "#444" }}>{status}</p>}

      {result && (
        <>
          <div style={{ display: "flex", gap: 16, alignItems: "center", margin: "8px 0" }}>
            <strong>{keptCount} to catalogue</strong>
            <button onClick={confirm} disabled={busy || keptCount === 0} style={{ padding: "8px 16px", fontWeight: 700 }}>
              Confirm {keptCount} stones
            </button>
            <span style={{ color: "#888" }}>numbers below = reading order (assigned as codes on confirm)</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 10 }}>
            {cands.map((s, i) => {
              const url = cropUrl(s);
              const order = cands.filter((x) => x.keep).findIndex((x) => x.id === s.id);
              return (
                <div key={s.id} style={{ border: "1px solid #ddd", borderRadius: 8, padding: 8, opacity: s.keep ? 1 : 0.4, background: s.keep ? "#fff" : "#f6f6f6" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                    <strong>{s.keep ? `#${order + 1}` : "rejected"}</strong>
                    <span>{s.width_cm} x {s.height_cm} cm</span>
                  </div>
                  {url && <img src={url} alt="" style={{ width: "100%", height: 90, objectFit: "contain", background: "#faf8f2" }} />}
                  <div style={{ display: "flex", gap: 4, marginTop: 6 }}>
                    <button onClick={() => move(i, -1)} disabled={i === 0}>&uarr;</button>
                    <button onClick={() => move(i, 1)} disabled={i === cands.length - 1}>&darr;</button>
                    <button onClick={() => toggleKeep(s.id)} style={{ marginLeft: "auto" }}>{s.keep ? "reject" : "keep"}</button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </main>
  );
}
