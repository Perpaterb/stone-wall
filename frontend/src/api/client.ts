export interface Project {
  id: string;
  name: string;
  kind: string;
  grout_min_cm: number;
  grout_max_cm: number;
  dummy_params: Record<string, unknown> | null;
  stone_counter: number;
  created_at: string;
}

export interface ProjectCreate {
  name: string;
  kind: string;
  grout_min_cm: number;
  grout_max_cm: number;
}

const BASE = "/api";

export async function listProjects(): Promise<Project[]> {
  const res = await fetch(`${BASE}/projects`);
  if (!res.ok) throw new Error(`Failed to load projects (${res.status})`);
  return res.json();
}

export async function createProject(input: ProjectCreate): Promise<Project> {
  const res = await fetch(`${BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Failed to create project (${res.status})`);
  return res.json();
}
