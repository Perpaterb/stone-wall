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
