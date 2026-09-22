import { describe, it, expect, vi, afterEach } from "vitest";
import { uploadPhoto, listSamplePhotos } from "./client";

afterEach(() => vi.restoreAllMocks());

describe("api client", () => {
  it("POSTs multipart to /api/photo and returns parsed body", async () => {
    const body = { photo_id: "abc", width: 10, height: 20, quality_checks: [], default_whole: { palette: [], coverage: [], material: "matte" } };
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
    vi.stubGlobal("fetch", fetchMock);
    const res = await uploadPhoto(new Blob(["x"]), "m.png");
    expect(res.photo_id).toBe("abc");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/photo");
    expect(opts.method).toBe("POST");
    expect(opts.body).toBeInstanceOf(FormData);
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404, text: async () => "nope" }));
    await expect(listSamplePhotos()).rejects.toThrow(/404/);
  });
});
