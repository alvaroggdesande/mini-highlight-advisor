import { create } from "zustand";
import type { PhotoResponse, Settings, Whole, PaintColor, QualityCheck } from "../api/types";
import { newId } from "../lib/id";

export const DEFAULT_SETTINGS: Settings = {
  edge_hl: true, edge_extreme: false, edge_sens: 0.5, relief_cap: true, per_region_norm: false,
};

export interface WholeState extends Whole {
  surface?: string;
  tone?: string;
  ramp_midtone?: string;
  ramp_variant?: string;
}

export interface DrawnRegion {
  id: string; name: string; rings: number[][][];
  palette: PaintColor[]; coverage: number[]; material: string; blank: boolean;
  surface?: string;
  tone?: string;
  ramp_midtone?: string;
  ramp_variant?: string;
}

export interface Scheme {
  id: string;
  name: string;
  palettes: { [regionId: string]: PaintColor[] };
  anchor_hex?: string;
}

export interface Book {
  whole: WholeState;
  drawn: DrawnRegion[];
  selected: number;
  hero_hex?: string;
  mood?: string;
  variant?: string;
  schemes: Scheme[];
}
export interface Angle {
  id: string; label: string;
  photoId?: string; width?: number; height?: number; qualityChecks: QualityCheck[];
  book: Book; settings: Settings;
  preview?: string; resultToken?: string; error?: string;
}

interface State {
  activeAngle: number;
  angles: Angle[];
  initFromPhoto(res: PhotoResponse): void;
  addAngle(res: PhotoResponse): void;
  switchAngle(i: number): void;
  renameAngle(i: number, label: string): void;
  removeAngle(i: number): void;
  setSelected(g: number): void;
  addRegion(rings: number[][][], name?: string): void;
  removeRegion(g: number): void;
  renameRegion(g: number, name: string): void;
  toggleBlank(g: number): void;
  setCoverage(cov: number[]): void;
  setBandCount(n: number): void;
  setPreview(png: string, token: string): void;
  setError(msg?: string): void;
  setSurface(g: number, surface: string): void;
  setTone(g: number, tone: string): void;
  setMaterial(g: number, material: string): void;
  setHeroHex(hex: string): void;
  setMood(mood: string): void;
  setVariant(variant: string): void;
  setRampState(g: number, midtone: string, variant: string): void;
  setPaletteAt(g: number, palette: PaintColor[]): void;
  setPaletteSlot(g: number, i: number, paint: PaintColor): void;
  setHexSlot(g: number, i: number, hex: string): void;
  saveScheme(name: string): void;
  applyScheme(id: string): void;
  deleteScheme(id: string): void;
}

export const activeAngleOf = (s: { angles: Angle[]; activeAngle: number }): Angle | undefined =>
  s.angles[s.activeAngle];
export const activeBookOf = (s: { angles: Angle[]; activeAngle: number }): Book | undefined =>
  activeAngleOf(s)?.book;

function makeAngle(res: PhotoResponse, label: string, settings: Settings): Angle {
  return {
    id: newId(), label, photoId: res.photo_id, width: res.width, height: res.height,
    qualityChecks: res.quality_checks,
    book: { whole: res.default_whole, drawn: [], selected: 0, schemes: [] },
    settings,
  };
}

function resize<T>(arr: T[], n: number, fill: (i: number) => T): T[] {
  const out = arr.slice(0, n);
  for (let i = out.length; i < n; i++) out.push(fill(i));
  return out;
}

// Immutably update the active angle's book.
function patchBook(s: State, fn: (b: Book) => Book): Partial<State> {
  const angle = s.angles[s.activeAngle];
  if (!angle) return {};
  const angles = s.angles.slice();
  angles[s.activeAngle] = { ...angle, book: fn(angle.book) };
  return { angles };
}
function patchAngle(s: State, i: number, fn: (a: Angle) => Angle): Partial<State> {
  const angle = s.angles[i];
  if (!angle) return {};
  const angles = s.angles.slice();
  angles[i] = fn(angle);
  return { angles };
}

function neutralRegion(book: Book): DrawnRegion {
  const n = book.whole.palette.length;
  return {
    id: newId(), name: "", rings: [],
    palette: Array.from({ length: n }, () => ({ name: "band", hex: "#808080" })),
    coverage: Array.from({ length: n }, () => 1 / n),
    material: "matte", blank: false,
  };
}

const INITIAL_STATE = { activeAngle: 0, angles: [] as Angle[] };

export const useProjectStore = create<State>((set) => ({
  ...INITIAL_STATE,

  initFromPhoto: (res) => set({ activeAngle: 0, angles: [makeAngle(res, "angle 1", DEFAULT_SETTINGS)] }),

  addAngle: (res) => set((s) => {
    const settings = s.angles[s.activeAngle]?.settings ?? DEFAULT_SETTINGS;
    const angles = s.angles.concat(makeAngle(res, `angle ${s.angles.length + 1}`, settings));
    return { angles, activeAngle: angles.length - 1 };
  }),

  switchAngle: (i) => set((s) => (i >= 0 && i < s.angles.length ? { activeAngle: i } : {})),

  renameAngle: (i, label) => set((s) => {
    const clean = label.trim();
    return clean ? patchAngle(s, i, (a) => ({ ...a, label: clean })) : {};
  }),

  removeAngle: (i) => set((s) => {
    if (s.angles.length <= 1) return {};
    const angles = s.angles.slice();
    angles.splice(i, 1);
    const activeAngle = s.activeAngle > i ? s.activeAngle - 1
      : s.activeAngle === i ? Math.max(0, i - 1) : s.activeAngle;
    return { angles, activeAngle };
  }),

  setSelected: (g) => set((s) => patchBook(s, (b) =>
    g >= 0 && g <= b.drawn.length ? { ...b, selected: g } : b)),

  addRegion: (rings, name) => set((s) => patchBook(s, (b) => {
    const region = { ...neutralRegion(b), rings, name: (name ?? `region ${b.drawn.length + 1}`).trim() };
    const drawn = b.drawn.concat(region);
    return { ...b, drawn, selected: drawn.length };
  })),

  removeRegion: (g) => set((s) => patchBook(s, (b) => {
    if (g < 1 || g > b.drawn.length) return b;
    const drawn = b.drawn.slice();
    drawn.splice(g - 1, 1);
    const selected = b.selected === g ? g - 1 : b.selected > g ? b.selected - 1 : b.selected;
    return { ...b, drawn, selected };
  })),

  renameRegion: (g, name) => set((s) => patchBook(s, (b) => {
    const clean = name.trim();
    if (g < 1 || g > b.drawn.length || !clean) return b;
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], name: clean };
    return { ...b, drawn };
  })),

  toggleBlank: (g) => set((s) => patchBook(s, (b) => {
    if (g < 1 || g > b.drawn.length) return b;
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], blank: !drawn[g - 1].blank };
    return { ...b, drawn };
  })),

  setCoverage: (cov) => set((s) => patchBook(s, (b) => {
    if (b.selected === 0) return { ...b, whole: { ...b.whole, coverage: cov } };
    const drawn = b.drawn.slice();
    drawn[b.selected - 1] = { ...drawn[b.selected - 1], coverage: cov };
    return { ...b, drawn };
  })),

  setBandCount: (n) => set((s) => patchBook(s, (b) => {
    const cur = b.selected === 0 ? b.whole : b.drawn[b.selected - 1];
    const palette = resize(cur.palette, n, () => ({ name: "band", hex: "#808080" }));
    const raw = resize(cur.coverage, n, () => 1 / n);
    const sum = raw.reduce((a, c) => a + c, 0);
    const coverage = sum > 0 ? raw.map((v) => v / sum) : raw.map(() => 1 / n);
    if (b.selected === 0) return { ...b, whole: { ...b.whole, palette, coverage } };
    const drawn = b.drawn.slice();
    drawn[b.selected - 1] = { ...drawn[b.selected - 1], palette, coverage };
    return { ...b, drawn };
  })),

  setPreview: (png, token) => set((s) =>
    patchAngle(s, s.activeAngle, (a) => ({ ...a, preview: png, resultToken: token, error: undefined }))),

  setError: (msg) => set((s) => patchAngle(s, s.activeAngle, (a) => ({ ...a, error: msg }))),

  setSurface: (g, surface) => set((s) => patchBook(s, (b) => {
    if (g === 0) return { ...b, whole: { ...b.whole, surface } };
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], surface };
    return { ...b, drawn };
  })),

  setTone: (g, tone) => set((s) => patchBook(s, (b) => {
    if (g === 0) return { ...b, whole: { ...b.whole, tone } };
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], tone };
    return { ...b, drawn };
  })),

  setMaterial: (g, material) => set((s) => patchBook(s, (b) => {
    if (g === 0) return { ...b, whole: { ...b.whole, material } };
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], material };
    return { ...b, drawn };
  })),

  setHeroHex: (hex) => set((s) => patchBook(s, (b) => ({ ...b, hero_hex: hex }))),

  setMood: (mood) => set((s) => patchBook(s, (b) => ({ ...b, mood }))),

  setVariant: (variant) => set((s) => patchBook(s, (b) => ({ ...b, variant }))),

  setRampState: (g, midtone, variant) => set((s) => patchBook(s, (b) => {
    if (g === 0) return { ...b, whole: { ...b.whole, ramp_midtone: midtone, ramp_variant: variant } };
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], ramp_midtone: midtone, ramp_variant: variant };
    return { ...b, drawn };
  })),

  setPaletteAt: (g, palette) => set((s) => patchBook(s, (b) => {
    if (g === 0) return { ...b, whole: { ...b.whole, palette } };
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], palette };
    return { ...b, drawn };
  })),

  setPaletteSlot: (g, i, paint) => set((s) => patchBook(s, (b) => {
    const region = g === 0 ? b.whole : b.drawn[g - 1];
    if (!region) return b;
    const palette = region.palette.slice();
    palette[i] = paint;
    if (g === 0) return { ...b, whole: { ...b.whole, palette } };
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], palette };
    return { ...b, drawn };
  })),

  setHexSlot: (g, i, hex) => set((s) => patchBook(s, (b) => {
    const region = g === 0 ? b.whole : b.drawn[g - 1];
    if (!region) return b;
    const palette = region.palette.slice();
    palette[i] = { name: "custom", hex, code: "", finish: palette[i]?.finish ?? "matte" };
    if (g === 0) return { ...b, whole: { ...b.whole, palette } };
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], palette };
    return { ...b, drawn };
  })),

  saveScheme: (name) => set((s) => patchBook(s, (b) => {
    const palettes: { [id: string]: PaintColor[] } = {};
    palettes["__whole__"] = b.whole.palette.slice();
    for (const r of b.drawn) palettes[r.id] = r.palette.slice();
    const scheme: Scheme = { id: newId(), name, palettes, anchor_hex: b.hero_hex };
    return { ...b, schemes: [...b.schemes, scheme] };
  })),

  applyScheme: (id) => set((s) => patchBook(s, (b) => {
    const scheme = b.schemes.find((sc) => sc.id === id);
    if (!scheme) return b;
    const wholePal = scheme.palettes["__whole__"];
    const whole = wholePal ? { ...b.whole, palette: wholePal.slice() } : b.whole;
    const drawn = b.drawn.map((r) => {
      const pal = scheme.palettes[r.id];
      return pal ? { ...r, palette: pal.slice() } : r;
    });
    return { ...b, whole, drawn };
  })),

  deleteScheme: (id) => set((s) => patchBook(s, (b) => ({
    ...b, schemes: b.schemes.filter((sc) => sc.id !== id),
  }))),
}));
