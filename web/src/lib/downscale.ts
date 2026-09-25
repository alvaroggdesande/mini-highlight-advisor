// Downscale a photo in the browser before upload so the backend never has to
// decode a full-resolution phone photo (a 12 MP JPEG is ~48 MB decoded, which
// spikes memory on the 512 MB Render free tier). The server downsamples to
// 768px for analysis anyway, so a generous cap here is lossless for the result.
//
// Defensive by design: any unsupported environment (no canvas / createImageBitmap,
// non-image blob, decode failure) returns the original blob unchanged.

const CAP = 1600;

export async function downscaleImage(blob: Blob, cap: number = CAP): Promise<Blob> {
  const mime = blob.type;
  if (mime !== "image/png" && mime !== "image/jpeg") return blob;
  if (typeof createImageBitmap !== "function" || typeof document === "undefined") return blob;

  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(blob, { imageOrientation: "from-image" });
  } catch {
    return blob; // undecodable — let the server deal with the original
  }

  try {
    const longest = Math.max(bitmap.width, bitmap.height);
    if (longest <= cap) return blob; // already small enough — keep original bytes

    const scale = cap / longest;
    const w = Math.round(bitmap.width * scale);
    const h = Math.round(bitmap.height * scale);
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx || typeof canvas.toBlob !== "function") return blob;
    ctx.drawImage(bitmap, 0, 0, w, h);

    const out = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, mime, mime === "image/jpeg" ? 0.9 : undefined),
    );
    return out ?? blob;
  } finally {
    bitmap.close();
  }
}
