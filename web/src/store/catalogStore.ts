import { create } from "zustand";
import { fetchCatalog, getCollection, putCollection } from "../api/client";
import type { PaintColor } from "../api/types";

interface CatalogState {
  paints: PaintColor[];
  status: "idle" | "loading" | "ready" | "error";
  error?: string;
  ownedCodes: Set<string>;
  collectionStatus: "idle" | "loading" | "ready" | "error";
  fetch(): Promise<void>;
  findByCode(code: string): PaintColor | undefined;
  loadCollection(): Promise<void>;
  toggleOwned(code: string): Promise<void>;
  setOwnedFromImport(codes: string[]): void;
}

export const useCatalogStore = create<CatalogState>((set, get) => ({
  paints: [],
  status: "idle",
  ownedCodes: new Set<string>(),
  collectionStatus: "idle",

  fetch: async () => {
    const { status } = get();
    if (status === "ready" || status === "loading") return;
    set({ status: "loading" });
    try {
      const res = await fetchCatalog();
      set({ paints: res.paints, status: "ready" });
    } catch (e) {
      set({ status: "error", error: String(e) });
    }
  },

  findByCode: (code) => get().paints.find((p) => p.code === code),

  loadCollection: async () => {
    const { collectionStatus } = get();
    if (collectionStatus === "ready" || collectionStatus === "loading") return;
    set({ collectionStatus: "loading" });
    try {
      const res = await getCollection();
      set({ ownedCodes: new Set(res.owned), collectionStatus: "ready" });
    } catch (e) {
      set({ collectionStatus: "error" });
    }
  },

  toggleOwned: async (code: string) => {
    const { ownedCodes } = get();
    const next = new Set(ownedCodes);
    if (next.has(code)) next.delete(code);
    else next.add(code);
    set({ ownedCodes: next });
    try {
      await putCollection([...next]);
    } catch {
      set({ ownedCodes }); // revert
    }
  },

  setOwnedFromImport: (codes: string[]) => {
    set({ ownedCodes: new Set(codes), collectionStatus: "ready" });
  },
}));
