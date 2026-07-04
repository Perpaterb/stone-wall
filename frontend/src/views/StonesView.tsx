import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  cropUrl,
  deleteStone,
  getPhoto,
  listStones,
  updateStone,
  type PhotoInfo,
  type Stone,
} from "../api/client";

const FILTERS = ["available", "hold_unless_needed", "used", "all"] as const;
type Filter = (typeof FILTERS)[number];

export default function StonesView() {
  const { projectId } = useParams();
  const [stones, setStones] = useState<Stone[]>([]);
  const [filter, setFilter] = useState<Filter>("available");
  const [selected, setSelected] = useState<Stone | null>(null);
  const [photo, setPhoto] = useState<PhotoInfo | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  function refresh() {
    if (!projectId) return;
    listStones(projectId).then(setStones).catch((e) => setStatus(String(e)));
  }

  useEffect(refresh, [projectId]);

  useEffect(() => {
    setPhoto(null);
    if (selected?.source_photo_id) {
      getPhoto(selected.source_photo_id).then(setPhoto).catch(() => setPhoto(null));
    }
  }, [selected]);

  const shown = useMemo(
    () => (filter === "all" ? stones : stones.filter((s) => s.status === filter)),
    [stones, filter]
  );

  async function patch(s: Stone, p: Parameters<typeof updateStone>[1]) {
    const updated = await updateStone(s.id, p);
    setStones((list) => list.map((x) => (x.id === updated.id ? updated : x)));
    setSelected((cur) => (cur?.id === updated.id ? updated : cur));
  }

  async function remove(s: Stone) {
    await deleteStone(s.id);
    setStones((list) => list.filter((x) => x.id !== s.id));
    setSelected(null);
  }

  return (
    <main style={{ maxWidth: 1100, margin: "1rem auto", padding: "0 1rem", fontFamily: "system-ui, sans-serif" }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <Link to="/">&larr; Projects</Link>
        {projectId && <Link to={`/projects/${projectId}/plan`}>Plan</Link>}
        {projectId && <Link to={`/projects/${projectId}/add-stones`}>Add stones</Link>}
        <h2 style={{ margin: "0 0 0 8px" }}>Catalogue</h2>
      </div>

      <div style={{ display: "flex", gap: 6, margin: "10px 0" }}>
        {FILTERS.map((f) => (
          <button key={f} onClick={() => setFilter(f)} style={{ fontWeight: filter === f ? 700 : 400, background: filter === f ? "#eef" : "#fff", padding: "4px 10px" }}>
            {f.replace(/_/g, " ")} ({f === "all" ? stones.length : stones.filter((s) => s.status === f).length})
          </button>
        ))}
      </div>
      {status && <p style={{ color: "crimson" }}>{status}</p>}

      <div style={{ display: "flex", gap: 16 }}>
        <div style={{ flex: 1, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: 8 }}>
          {shown.map((s) => {
            const url = cropUrl(s);
            return (
              <div key={s.id} onClick={() => setSelected(s)} style={{ border: selected?.id === s.id ? "2px solid #2b6cb0" : "1px solid #ddd", borderRadius: 8, padding: 6, cursor: "pointer" }}>
                <div style={{ fontSize: 12, display: "flex", justifyContent: "space-between" }}>
                  <strong>{s.code || "pending"}</strong>
                  <span>{s.width_cm}x{s.height_cm}</span>
                </div>
                {url ? (
                  <img src={url} alt="" style={{ width: "100%", height: 70, objectFit: "contain", background: "#faf8f2" }} />
                ) : (
                  <div style={{ height: 70, background: "#eee", display: "flex", alignItems: "center", justifyContent: "center", color: "#999", fontSize: 11 }}>no image</div>
                )}
              </div>
            );
          })}
          {shown.length === 0 && <p style={{ color: "#999" }}>No stones in this view.</p>}
        </div>

        {selected && (
          <div style={{ width: 320, border: "1px solid #ddd", borderRadius: 8, padding: 12, alignSelf: "flex-start" }}>
            <h3 style={{ marginTop: 0 }}>{selected.code || "pending"}</h3>
            {cropUrl(selected) && <img src={cropUrl(selected)!} alt="" style={{ width: "100%", maxHeight: 180, objectFit: "contain", background: "#faf8f2" }} />}
            <p style={{ margin: "8px 0" }}>
              {selected.width_cm} x {selected.height_cm} cm, area {selected.area_cm2} cm&sup2;
              <br />
              status: <strong>{selected.status}</strong>
            </p>
            <label style={{ display: "block", fontSize: 13 }}>
              Label
              <input defaultValue={selected.label ?? ""} style={{ width: "100%" }} onBlur={(e) => patch(selected, { label: e.target.value })} />
            </label>
            <label style={{ display: "block", fontSize: 13, marginTop: 6 }}>
              Notes
              <textarea defaultValue={selected.notes} style={{ width: "100%" }} onBlur={(e) => patch(selected, { notes: e.target.value })} />
            </label>
            <label style={{ display: "block", fontSize: 13, marginTop: 6 }}>
              Storage
              <input defaultValue={selected.storage_location ?? ""} style={{ width: "100%" }} onBlur={(e) => patch(selected, { storage_location: e.target.value })} />
            </label>
            <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
              {selected.status !== "hold_unless_needed" ? (
                <button onClick={() => patch(selected, { status: "hold_unless_needed" })}>Hold</button>
              ) : (
                <button onClick={() => patch(selected, { status: "available" })}>Release</button>
              )}
              <button onClick={() => remove(selected)} style={{ color: "crimson" }}>Delete</button>
            </div>

            {photo && selected.sheet_x_cm != null && selected.sheet_y_cm != null && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>In source photo:</div>
                <div style={{ position: "relative", width: "100%" }}>
                  <img src={photo.warped_url} alt="" style={{ width: "100%", display: "block", border: "1px solid #ccc" }} />
                  <div
                    style={{
                      position: "absolute",
                      border: "2px solid #e53e3e",
                      left: `${((selected.sheet_x_cm - selected.width_cm / 2) / photo.span_x_cm) * 100}%`,
                      top: `${((selected.sheet_y_cm - selected.height_cm / 2) / photo.span_y_cm) * 100}%`,
                      width: `${(selected.width_cm / photo.span_x_cm) * 100}%`,
                      height: `${(selected.height_cm / photo.span_y_cm) * 100}%`,
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
