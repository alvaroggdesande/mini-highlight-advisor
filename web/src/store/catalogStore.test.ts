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

describe("catalogStore — collection", () => {
  const reset = () =>
    useCatalogStore.setState({
      paints: [],
      status: "idle",
      error: undefined,
      ownedCodes: new Set(),
      collectionStatus: "idle",
    });

  beforeEach(() => {
    reset();
    vi.restoreAllMocks();
  });

  it("loadCollection transitions idle → loading → ready and stores codes", async () => {
    vi.spyOn(client, "getCollection").mockResolvedValue({ owned: ["X1", "X2"] });
    expect(useCatalogStore.getState().collectionStatus).toBe("idle");
    await useCatalogStore.getState().loadCollection();
    const s = useCatalogStore.getState();
    expect(s.collectionStatus).toBe("ready");
    expect(s.ownedCodes).toEqual(new Set(["X1", "X2"]));
  });

  it("loadCollection is idempotent — second call is a no-op", async () => {
    const spy = vi.spyOn(client, "getCollection").mockResolvedValue({ owned: ["X1"] });
    await useCatalogStore.getState().loadCollection();
    await useCatalogStore.getState().loadCollection();
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("toggleOwned adds a code and persists", async () => {
    vi.spyOn(client, "getCollection").mockResolvedValue({ owned: [] });
    vi.spyOn(client, "putCollection").mockResolvedValue({ ok: true });
    await useCatalogStore.getState().loadCollection();
    await useCatalogStore.getState().toggleOwned("C1");
    const s = useCatalogStore.getState();
    expect(s.ownedCodes.has("C1")).toBe(true);
    expect(client.putCollection).toHaveBeenCalledWith(expect.arrayContaining(["C1"]));
  });

  it("toggleOwned removes an already-owned code and persists", async () => {
    vi.spyOn(client, "getCollection").mockResolvedValue({ owned: ["C1", "C2"] });
    vi.spyOn(client, "putCollection").mockResolvedValue({ ok: true });
    await useCatalogStore.getState().loadCollection();
    await useCatalogStore.getState().toggleOwned("C1");
    const s = useCatalogStore.getState();
    expect(s.ownedCodes.has("C1")).toBe(false);
    expect(s.ownedCodes.has("C2")).toBe(true);
    expect(client.putCollection).toHaveBeenCalledWith(expect.arrayContaining(["C2"]));
    expect(client.putCollection).toHaveBeenCalledWith(expect.not.arrayContaining(["C1"]));
  });

  it("toggleOwned reverts on API error", async () => {
    vi.spyOn(client, "getCollection").mockResolvedValue({ owned: [] });
    vi.spyOn(client, "putCollection").mockRejectedValue(new Error("network"));
    await useCatalogStore.getState().loadCollection();
    await useCatalogStore.getState().toggleOwned("C1");
    expect(useCatalogStore.getState().ownedCodes.has("C1")).toBe(false);
  });

  it("setOwnedFromImport replaces the owned set", async () => {
    vi.spyOn(client, "getCollection").mockResolvedValue({ owned: ["OLD"] });
    await useCatalogStore.getState().loadCollection();
    useCatalogStore.getState().setOwnedFromImport(["NEW1", "NEW2"]);
    const s = useCatalogStore.getState();
    expect(s.ownedCodes).toEqual(new Set(["NEW1", "NEW2"]));
  });

  it("loadCollection sets error on rejection", async () => {
    vi.spyOn(client, "getCollection").mockRejectedValue(new Error("net"));
    await useCatalogStore.getState().loadCollection();
    expect(useCatalogStore.getState().collectionStatus).toBe("error");
  });
});
