import { describe, it, expect, beforeEach, vi } from "vitest";
import { useCatalogStore } from "./catalogStore";
import * as client from "../api/client";
import type { PaintColor } from "../api/types";

const reset = () => useCatalogStore.setState({ paints: [], status: "idle", error: undefined });
const fakePaint = (code: string): PaintColor => ({ name: "P", hex: "#aabbcc", code, finish: "matte" });

describe("catalogStore", () => {
  beforeEach(() => {
    reset();
    vi.restoreAllMocks();
  });

  it("fetch transitions idle → loading → ready", async () => {
    vi.spyOn(client, "fetchCatalog").mockResolvedValue({ paints: [fakePaint("X1")] });
    expect(useCatalogStore.getState().status).toBe("idle");
    await useCatalogStore.getState().fetch();
    const s = useCatalogStore.getState();
    expect(s.status).toBe("ready");
    expect(s.paints).toHaveLength(1);
  });

  it("fetch is idempotent — second call is a no-op", async () => {
    const spy = vi.spyOn(client, "fetchCatalog").mockResolvedValue({ paints: [fakePaint("X1")] });
    await useCatalogStore.getState().fetch();
    await useCatalogStore.getState().fetch();
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("findByCode returns matching paint", async () => {
    vi.spyOn(client, "fetchCatalog").mockResolvedValue({ paints: [fakePaint("X1"), fakePaint("X2")] });
    await useCatalogStore.getState().fetch();
    expect(useCatalogStore.getState().findByCode("X2")).toMatchObject({ code: "X2" });
    expect(useCatalogStore.getState().findByCode("NOPE")).toBeUndefined();
  });

  it("fetch sets error status on rejection", async () => {
    vi.spyOn(client, "fetchCatalog").mockRejectedValue(new Error("network"));
    await useCatalogStore.getState().fetch();
    expect(useCatalogStore.getState().status).toBe("error");
  });
});
