import type { AnalyzeRequest, AnalyzeResponse, PhotoResponse, SamplePhoto, StepsResponse } from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export class TokenExpiredError extends Error {
  constructor() { super("token expired"); }
}

export async function uploadPhoto(file: Blob, name = "upload.png"): Promise<PhotoResponse> {
  const fd = new FormData();
  fd.append("file", file, name);
  return json<PhotoResponse>(await fetch("/api/photo", { method: "POST", body: fd }));
}

export async function analyze(req: AnalyzeRequest): Promise<AnalyzeResponse> {
  return json<AnalyzeResponse>(await fetch("/api/analyze", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
  }));
}

export async function listSamplePhotos(): Promise<SamplePhoto[]> {
  return json<SamplePhoto[]>(await fetch("/api/samples/photos"));
}

export async function samplePhotoBlob(id: string): Promise<Blob> {
  const res = await fetch(`/api/samples/photos/${id}`);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.blob();
}

import type {
  CatalogResponse, MatchRequest, MatchResult,
  SchemeGenerateRequest, SchemeGenerateResponse,
  RampGenerateRequest, RampGenerateResponse,
  Recipe,
} from "./types";

export async function fetchCatalog(): Promise<CatalogResponse> {
  return json<CatalogResponse>(await fetch("/api/catalog"));
}

export async function matchPaint(req: MatchRequest): Promise<MatchResult> {
  return json<MatchResult>(await fetch("/api/match", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
  }));
}

export async function generateScheme(req: SchemeGenerateRequest): Promise<SchemeGenerateResponse> {
  return json<SchemeGenerateResponse>(await fetch("/api/scheme/generate", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
  }));
}

export async function generateRamp(req: RampGenerateRequest): Promise<RampGenerateResponse> {
  return json<RampGenerateResponse>(await fetch("/api/ramp/generate", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
  }));
}

export async function listRecipes(): Promise<{ recipes: Recipe[] }> {
  return json<{ recipes: Recipe[] }>(await fetch("/api/recipes"));
}

export async function saveRecipe(recipe: Recipe): Promise<{ ok: boolean }> {
  return json<{ ok: boolean }>(await fetch("/api/recipes", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(recipe),
  }));
}

export async function exportRecipes(): Promise<Blob> {
  const res = await fetch("/api/recipes/export");
  if (!res.ok) throw new Error(`${res.status}`);
  return res.blob();
}

export async function importRecipes(file: File): Promise<{ recipes: Recipe[] }> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  return json<{ recipes: Recipe[] }>(await fetch("/api/recipes/import", { method: "POST", body: fd }));
}

export async function getCollection(): Promise<{ owned: string[] }> {
  return json<{ owned: string[] }>(await fetch("/api/collection"));
}

export async function putCollection(owned: string[]): Promise<{ ok: boolean }> {
  return json<{ ok: boolean }>(await fetch("/api/collection", {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ owned }),
  }));
}

export async function exportCollection(): Promise<Blob> {
  const res = await fetch("/api/collection/export");
  if (!res.ok) throw new Error(`${res.status}`);
  return res.blob();
}

export async function importCollection(file: File): Promise<{ owned: string[] }> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  return json<{ owned: string[] }>(await fetch("/api/collection/import", { method: "POST", body: fd }));
}

export async function fetchSteps(token: string): Promise<StepsResponse> {
  const res = await fetch(`/api/steps?token=${encodeURIComponent(token)}`);
  if (res.status === 409) throw new TokenExpiredError();
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<StepsResponse>;
}

import type { ProjectMeta, ProjectManifestDto } from "./types";
import type { Angle } from "../store/projectStore";

function toProjectAngleDto(a: Angle): object {
  return {
    id: a.id,
    label: a.label,
    photo_id: a.photoId,
    width: a.width,
    height: a.height,
    book: a.book,
    settings: a.settings,
  };
}

export async function listProjects(): Promise<ProjectMeta[]> {
  const data = await json<{ projects: ProjectMeta[] }>(await fetch("/api/projects"));
  return data.projects;
}

export async function saveProjectApi(
  name: string,
  activeAngle: number,
  angles: Angle[],
): Promise<{ slug: string; name: string; updated_at: string }> {
  return json(await fetch("/api/projects", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, active_angle: activeAngle, angles: angles.map(toProjectAngleDto) }),
  }));
}

export async function loadProjectApi(slug: string): Promise<ProjectManifestDto> {
  return json<ProjectManifestDto>(await fetch(`/api/projects/${encodeURIComponent(slug)}`));
}

export async function deleteProjectApi(slug: string): Promise<void> {
  await json(await fetch(`/api/projects/${encodeURIComponent(slug)}`, { method: "DELETE" }));
}

export async function downloadProjectBlob(slug: string): Promise<void> {
  const res = await fetch(`/api/projects/${encodeURIComponent(slug)}/download`);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${slug}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function uploadProjectBlob(file: File): Promise<ProjectManifestDto> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  return json<ProjectManifestDto>(await fetch("/api/projects/upload", { method: "POST", body: fd }));
}
