export interface PaintColor {
  name: string; hex: string; brand?: string | null;
  paint_range?: string | null; code?: string; finish?: string;
}
export interface Whole { palette: PaintColor[]; coverage: number[]; material: string; }
export interface Settings {
  edge_hl: boolean; edge_extreme: boolean; edge_sens: number;
  relief_cap: boolean; per_region_norm: boolean;
}
export interface RegionPayload {
  name: string; rings: number[][][];
  palette: PaintColor[]; coverage: number[]; material: string;
}
export interface AnalyzeRequest {
  photo_id: string; whole: Whole; regions: RegionPayload[]; settings?: Partial<Settings>;
}
export interface QualityCheck { label: string; ok: boolean; detail: string; }
export interface PhotoResponse {
  photo_id: string; width: number; height: number;
  quality_checks: QualityCheck[]; default_whole: Whole;
}
export interface AnalyzeResponse { preview_png: string; result_token: string; }
export interface SamplePhoto { id: string; name: string; }

// Colour-panel request/response types
export interface RegionColorSpec {
  region_name: string; surface: string; tone?: string;
  n_bands: number; is_anchor: boolean;
}
export interface SchemeGenerateRequest {
  specs: RegionColorSpec[]; anchor_name: string; anchor_hex: string;
  mood: string; variant: string; owned_codes: string[];
}
export interface SchemeGenerateResponse {
  palettes: { [region_name: string]: PaintColor[] };
}
export interface RampGenerateRequest {
  midtone_hex?: string; n: number; variant: string;
  blend_hexes?: [string, string];
}
export interface RampGenerateResponse { hexes: string[]; }
export interface MatchRequest { hex: string; finish: string; owned_codes: string[]; }
export interface MatchResult {
  tier: string; phrase: string; name?: string; hex?: string; delta_e: number;
}
export interface RecipeStep { label: string; hex: string; paint_ref?: string | null; }
export interface Recipe { name: string; steps: RecipeStep[]; }
export interface CatalogResponse { paints: PaintColor[]; }

// Constants (mirrors Python)
export const MOODS = ["neutral", "grimdark", "heroic", "natural"] as const;
export const VARIANTS = ["complementary", "analogous", "triadic", "split-complementary"] as const;
export const RAMP_VARIANTS = ["ramp", "complementary", "warm", "cool"] as const;
export const SURFACES = [
  "skin", "bone", "metal", "wood", "leather", "fur", "cloth",
  "cloak", "robe", "gem", "accent", "other",
] as const;

export interface StepImageDto {
  index: number;
  label: string;
  kind: string;  // "band" | "edge" | "shade"
  zone_png: string;
  cumulative_png: string;
  exact_png: string | null;
  is_last: boolean;
}

export interface RegionPlanDto {
  name: string;
  roles: string[];
  coverage: number[];
  steps: StepImageDto[];
}

export interface StepsResponse {
  plans: RegionPlanDto[];
}

export interface ProjectMeta {
  slug: string;
  name: string;
  updated_at: string;
}

export interface ProjectAngleDto {
  id: string;
  label: string;
  photo_id: string;
  width?: number;
  height?: number;
  book: {
    whole: Whole;
    drawn: {
      id: string; name: string; rings: number[][][];
      palette: PaintColor[]; coverage: number[]; material: string;
      blank?: boolean;
      surface?: string; tone?: string; ramp_midtone?: string; ramp_variant?: string;
    }[];
    selected: number;
    hero_hex?: string;
    mood?: string;
    variant?: string;
    schemes: { id: string; name: string; palettes: { [regionId: string]: PaintColor[] }; anchor_hex?: string }[];
  };
  settings: Settings;
}

export interface ProjectManifestDto {
  name: string;
  slug: string;
  active_angle: number;
  updated_at: string;
  angles: ProjectAngleDto[];
}
