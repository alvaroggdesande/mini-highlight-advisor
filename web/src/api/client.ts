import type { AnalyzeRequest, AnalyzeResponse, PhotoResponse, SamplePhoto, StepsResponse, PlansManifest } from "./types";

// The free host sits behind Cloudflare, which answers request bursts with
// 429 (or 503 while the instance wakes). Retry those a few times with backoff,
// honouring Retry-After, before surfacing the error.
const RETRY_STATUSES = new Set([429, 503]);
const RETRY_DELAYS_MS = [1000, 2000, 4000];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function retryDelay(res: Response, attempt: number): number {
  const header = Number(res.headers?.get("Retry-After"));
  if (Number.isFinite(header) && header > 0) return Math.min(header, 10) * 1000;
  return RETRY_DELAYS_MS[attempt];
}

export async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  for (let attempt = 0; ; attempt++) {
    const res = await fetch(input, init);
    if (!RETRY_STATUSES.has(res.status) || attempt >= RETRY_DELAYS_MS.length) return res;
    await sleep(retryDelay(res, attempt));
  }
}

/** Error text for a failed response; HTML pages (e.g. Cloudflare challenges) are
 *  replaced by a short message instead of dumping markup into the UI. */
async function errorText(res: Response): Promise<string> {
  const body = await res.text();
  if (/^\s*</.test(body)) {
    return res.status === 429 || res.status === 503
      ? `${res.status} The server is busy — wait a moment and try again.`
      : `${res.status} Unexpected server response.`;
  }
  return `${res.status} ${body}`;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(await errorText(res));
  return res.json() as Promise<T>;
}

export class TokenExpiredError extends Error {
  constructor() { super("token expired"); }
}

export class PhotoExpiredError extends Error {
  constructor() {
    super("The app restarted while you were working — re-upload your photo to continue.");
  }
}

export async function uploadPhoto(file: Blob, name = "upload.png"): Promise<PhotoResponse> {
  const fd = new FormData();
  fd.append("file", file, name);
  return json<PhotoResponse>(await apiFetch("/api/photo", { method: "POST", body: fd }));
}

export async function analyze(req: AnalyzeRequest): Promise<AnalyzeResponse> {
  return json<AnalyzeResponse>(await apiFetch("/api/analyze", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
  }));
}

export async function listSamplePhotos(): Promise<SamplePhoto[]> {
  return json<SamplePhoto[]>(await apiFetch("/api/samples/photos"));
}

export async function samplePhotoBlob(id: string): Promise<Blob> {
  const res = await apiFetch(`/api/samples/photos/${id}`);
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
  return json<CatalogResponse>(await apiFetch("/api/catalog"));
}

export async function matchPaint(req: MatchRequest): Promise<MatchResult> {
  return json<MatchResult>(await apiFetch("/api/match", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
  }));
}

export async function generateScheme(req: SchemeGenerateRequest): Promise<SchemeGenerateResponse> {
  return json<SchemeGenerateResponse>(await apiFetch("/api/scheme/generate", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
  }));
}

export async function generateRamp(req: RampGenerateRequest): Promise<RampGenerateResponse> {
  return json<RampGenerateResponse>(await apiFetch("/api/ramp/generate", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
  }));
}

export async function listRecipes(): Promise<{ recipes: Recipe[] }> {
  return json<{ recipes: Recipe[] }>(await apiFetch("/api/recipes"));
}

export async function saveRecipe(recipe: Recipe): Promise<{ ok: boolean }> {
  return json<{ ok: boolean }>(await apiFetch("/api/recipes", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(recipe),
  }));
}

export async function exportRecipes(): Promise<Blob> {
  const res = await apiFetch("/api/recipes/export");
  if (!res.ok) throw new Error(`${res.status}`);
  return res.blob();
}

export async function importRecipes(file: File): Promise<{ recipes: Recipe[] }> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  return json<{ recipes: Recipe[] }>(await apiFetch("/api/recipes/import", { method: "POST", body: fd }));
}

export async function getCollection(): Promise<{ owned: string[] }> {
  return json<{ owned: string[] }>(await apiFetch("/api/collection"));
}

export async function putCollection(owned: string[]): Promise<{ ok: boolean }> {
  return json<{ ok: boolean }>(await apiFetch("/api/collection", {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ owned }),
  }));
}

export async function exportCollection(): Promise<Blob> {
  const res = await apiFetch("/api/collection/export");
  if (!res.ok) throw new Error(`${res.status}`);
  return res.blob();
}

export async function importCollection(file: File): Promise<{ owned: string[] }> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  return json<{ owned: string[] }>(await apiFetch("/api/collection/import", { method: "POST", body: fd }));
}

export async function fetchSteps(token: string, plan?: string): Promise<StepsResponse> {
  let url = `/api/steps?token=${encodeURIComponent(token)}`;
  if (plan !== undefined) url += `&plan=${encodeURIComponent(plan)}`;
  const res = await apiFetch(url);
  if (res.status === 409) throw new TokenExpiredError();
  if (!res.ok) throw new Error(await errorText(res));
  return res.json() as Promise<StepsResponse>;
}

export async function fetchPlanNames(token: string): Promise<PlansManifest> {
  const res = await apiFetch(`/api/plans?token=${encodeURIComponent(token)}`);
  if (res.status === 409) throw new TokenExpiredError();
  if (!res.ok) throw new Error(await errorText(res));
  return res.json() as Promise<PlansManifest>;
}

import type { ProjectMeta, ProjectManifestDto } from "./types";
import type { Angle } from "../store/projectStore";

function toProjectAngleDto(a: Angle): object {
  // anchor_id (★) is runtime-only: a loaded project always starts with the ★ on whole mini.
  const { anchor_id: _anchor, ...book } = a.book;
  return {
    id: a.id,
    label: a.label,
    photo_id: a.photoId,
    width: a.width,
    height: a.height,
    book,
    settings: a.settings,
  };
}

export async function listProjects(): Promise<ProjectMeta[]> {
  const data = await json<{ projects: ProjectMeta[] }>(await apiFetch("/api/projects"));
  return data.projects;
}

export async function saveProjectApi(
  name: string,
  activeAngle: number,
  angles: Angle[],
): Promise<{ slug: string; name: string; updated_at: string }> {
  const res = await apiFetch("/api/projects", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, active_angle: activeAngle, angles: angles.map(toProjectAngleDto) }),
  });
  if (res.status === 409) throw new PhotoExpiredError();
  return json(res);
}

export async function loadProjectApi(slug: string): Promise<ProjectManifestDto> {
  return json<ProjectManifestDto>(await apiFetch(`/api/projects/${encodeURIComponent(slug)}`));
}

export async function deleteProjectApi(slug: string): Promise<void> {
  await json(await apiFetch(`/api/projects/${encodeURIComponent(slug)}`, { method: "DELETE" }));
}

export async function downloadProjectBlob(slug: string): Promise<void> {
  const res = await apiFetch(`/api/projects/${encodeURIComponent(slug)}/download`);
  if (!res.ok) throw new Error(await errorText(res));
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
  return json<ProjectManifestDto>(await apiFetch("/api/projects/upload", { method: "POST", body: fd }));
}
