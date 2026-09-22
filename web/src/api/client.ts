import type { AnalyzeRequest, AnalyzeResponse, PhotoResponse, SamplePhoto } from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
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
