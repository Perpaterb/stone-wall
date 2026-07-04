import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { createProject, listProjects, type Project } from "../api/client";

export default function ProjectsView() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    try {
      setProjects(await listProjects());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await createProject({
        name: name.trim(),
        kind: "dummy",
        grout_min_cm: 1,
        grout_max_cm: 3,
      });
      setName("");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <main
      style={{
        maxWidth: 640,
        margin: "2rem auto",
        padding: "0 1rem",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <h1>Sandstone Wall Builder</h1>
      <p style={{ color: "#666" }}>M0 scaffold: project create / list round trip.</p>

      <form onSubmit={onCreate} style={{ display: "flex", gap: 8, margin: "1rem 0" }}>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New project name"
          style={{ flex: 1, padding: 8 }}
        />
        <button type="submit" style={{ padding: "8px 16px" }}>
          Create
        </button>
      </form>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {loading ? (
        <p>Loading...</p>
      ) : projects.length === 0 ? (
        <p style={{ color: "#666" }}>No projects yet. Create one above.</p>
      ) : (
        <ul style={{ lineHeight: 1.8 }}>
          {projects.map((p) => (
            <li key={p.id} style={{ marginBottom: 6 }}>
              <strong>{p.name}</strong> ({p.kind}) grout {p.grout_min_cm}-{p.grout_max_cm} cm
              <br />
              <span style={{ fontSize: 13 }}>
                <Link to={`/projects/${p.id}/plan`}>Plan</Link>
                {" · "}
                <Link to={`/projects/${p.id}/stones`}>Catalogue</Link>
                {" · "}
                <Link to={`/projects/${p.id}/add-stones`}>Add stones</Link>
              </span>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
