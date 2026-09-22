import { create } from "zustand";
import { fetchCatalog } from "../api/client";
import type { PaintColor } from "../api/types";

interface CatalogState {
  paints: PaintColor[];
  status: "idle" | "loading" | "ready" | "error";
  error?: string;
  fetch(): Promise<void>;
  findByCode(code: string): PaintColor | undefined;
}

export const useCatalogStore = create<CatalogState>((set, get) => ({
  paints: [],
  status: "idle",

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
}));
