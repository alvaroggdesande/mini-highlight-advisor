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

import { fetchSteps, fetchPlanNames, TokenExpiredError } from "./client";

describe("fetchSteps", () => {
  afterEach(() => vi.restoreAllMocks());

  it("throws TokenExpiredError on 409", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 409, ok: false }));
    await expect(fetchSteps("bad-token")).rejects.toBeInstanceOf(TokenExpiredError);
  });

  it("returns parsed JSON on 200", async () => {
    const body = { plans: [] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      status: 200, ok: true, json: () => Promise.resolve(body),
    }));
    const result = await fetchSteps("good-token");
    expect(result).toEqual(body);
  });

  it("adds the plan query param when a region is given", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 200, ok: true, json: () => Promise.resolve({ plans: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);
    await fetchSteps("good-token", "Whole mini");
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("token=good-token");
    expect(url).toContain("plan=Whole%20mini");
  });

  it("omits the plan query param when no region is given", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 200, ok: true, json: () => Promise.resolve({ plans: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);
    await fetchSteps("good-token");
    expect(fetchMock.mock.calls[0][0] as string).not.toContain("plan=");
  });
});

describe("fetchPlanNames", () => {
  afterEach(() => vi.restoreAllMocks());

  it("throws TokenExpiredError on 409", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 409, ok: false }));
    await expect(fetchPlanNames("bad-token")).rejects.toBeInstanceOf(TokenExpiredError);
  });

  it("GETs /api/plans and returns the parsed manifest", async () => {
    const body = { plans: [{ name: "Whole mini" }, { name: "Cloak" }] };
    const fetchMock = vi.fn().mockResolvedValue({
      status: 200, ok: true, json: () => Promise.resolve(body),
    });
    vi.stubGlobal("fetch", fetchMock);
    const result = await fetchPlanNames("good-token");
    expect(result).toEqual(body);
    expect(fetchMock.mock.calls[0][0] as string).toContain("/api/plans?token=good-token");
  });
});
