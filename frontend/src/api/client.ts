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

export async function getProject(id: string): Promise<Project> {
  const res = await fetch(`${BASE}/projects/${id}`);
  if (!res.ok) throw new Error(`Failed to load project (${res.status})`);
  return res.json();
}

export async function updateProject(
  id: string,
  patch: Partial<Pick<Project, "name" | "grout_min_cm" | "grout_max_cm">>
): Promise<Project> {
  const res = await fetch(`${BASE}/projects/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(`Failed to update project (${res.status})`);
  return res.json();
}

export interface PlanShape {
  id?: string;
  kind: "wall" | "negative";
  polygon: number[][];
  z_order?: number;
}

export interface Coverage {
  wall_area_cm2: number;
  negative_area_cm2: number;
  net_wall_area_cm2: number;
  stone_area_cm2: number;
  stone_count: number;
  coverage_ratio: number;
}

export async function getPlan(projectId: string): Promise<{ shapes: PlanShape[] }> {
  const res = await fetch(`${BASE}/projects/${projectId}/plan`);
  if (!res.ok) throw new Error(`Failed to load plan (${res.status})`);
  return res.json();
}

export async function putPlan(
  projectId: string,
  shapes: PlanShape[]
): Promise<{ shapes: PlanShape[] }> {
  const res = await fetch(`${BASE}/projects/${projectId}/plan`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ shapes }),
  });
  if (!res.ok) throw new Error(`Failed to save plan (${res.status})`);
  return res.json();
}

export async function getCoverage(projectId: string): Promise<Coverage> {
  const res = await fetch(`${BASE}/projects/${projectId}/coverage`);
  if (!res.ok) throw new Error(`Failed to load coverage (${res.status})`);
  return res.json();
}

export interface BuildMapSummary {
  id: string;
  name: string;
  seed: number;
  report: Record<string, number> | null;
  share_key: string;
  created_at: string;
}

export interface Placement {
  stone_id: string;
  code: string;
  x_cm: number;
  y_cm: number;
  w_cm: number;
  h_cm: number;
  rotation_deg: number;
  course_index: number;
  cut: Record<string, unknown> | null;
}

export interface BuildMapDetail extends BuildMapSummary {
  project_id: string;
  placements: Placement[];
}

export async function generateDummyStones(
  projectId: string,
  body: { count: number; seed: number }
): Promise<{ created: number; total: number }> {
  const res = await fetch(`${BASE}/projects/${projectId}/stones/generate-dummy`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed to generate stones (${res.status})`);
  return res.json();
}

export async function clearStones(projectId: string): Promise<{ deleted: number }> {
  const res = await fetch(`${BASE}/projects/${projectId}/stones`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to clear stones (${res.status})`);
  return res.json();
}

export async function createBuildMap(
  projectId: string,
  body: { name?: string; seed?: number }
): Promise<BuildMapSummary> {
  const res = await fetch(`${BASE}/projects/${projectId}/buildmaps`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Failed to create build map (${res.status})`);
  }
  return res.json();
}

export async function listBuildMaps(projectId: string): Promise<BuildMapSummary[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/buildmaps`);
  if (!res.ok) throw new Error(`Failed to list build maps (${res.status})`);
  return res.json();
}

export async function getBuildMap(id: string): Promise<BuildMapDetail> {
  const res = await fetch(`${BASE}/buildmaps/${id}`);
  if (!res.ok) throw new Error(`Failed to load build map (${res.status})`);
  return res.json();
}

export async function deleteBuildMap(id: string): Promise<void> {
  const res = await fetch(`${BASE}/buildmaps/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete build map (${res.status})`);
}
