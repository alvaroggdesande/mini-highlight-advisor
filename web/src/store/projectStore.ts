import { create } from "zustand";
import type { PhotoResponse, Settings, Whole } from "../api/types";

export const DEFAULT_SETTINGS: Settings = {
  edge_hl: true, edge_extreme: false, edge_sens: 0.5,
  relief_cap: true, per_region_norm: false,
};

interface State {
  photoId?: string; width?: number; height?: number;
  whole?: Whole; settings: Settings;
  preview?: string; resultToken?: string; error?: string;
  setPhoto(res: PhotoResponse): void;
  setCoverage(cov: number[]): void;
  setBandCount(n: number): void;
  setPreview(png: string, token: string): void;
  setError(msg?: string): void;
}

function resize<T>(arr: T[], n: number, fill: (i: number) => T): T[] {
  const out = arr.slice(0, n);
  for (let i = out.length; i < n; i++) out.push(fill(i));
  return out;
}

const initialState = {
  photoId: undefined,
  width: undefined,
  height: undefined,
  whole: undefined,
  settings: DEFAULT_SETTINGS,
  preview: undefined,
  resultToken: undefined,
  error: undefined,
};

export const useProjectStore = create<State>((set) => ({
  ...initialState,
  setPhoto: (res) => set({
    photoId: res.photo_id, width: res.width, height: res.height,
    whole: res.default_whole, preview: undefined, error: undefined,
  }),
  setCoverage: (cov) => set((s) => (s.whole ? { whole: { ...s.whole, coverage: cov } } : {})),
  setBandCount: (n) => set((s) => {
    if (!s.whole) return {};
    const palette = resize(s.whole.palette, n, () => ({ name: "band", hex: "#808080" }));
    const raw = resize(s.whole.coverage, n, () => 1 / n);
    const sum = raw.reduce((a, b) => a + b, 0);
    const coverage = sum > 0 ? raw.map((v) => v / sum) : raw.map(() => 1 / n);
    return { whole: { ...s.whole, palette, coverage } };
  }),
  setPreview: (png, token) => set({ preview: png, resultToken: token, error: undefined }),
  setError: (msg) => set({ error: msg }),
}));
