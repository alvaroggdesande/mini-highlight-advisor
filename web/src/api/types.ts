export interface PaintColor {
  name: string; hex: string; brand?: string | null;
  paint_range?: string | null; code?: string; finish?: string;
}
export interface Whole { palette: PaintColor[]; coverage: number[]; material: string; }
export interface Settings {
  edge_hl: boolean; edge_extreme: boolean; edge_sens: number;
  relief_cap: boolean; per_region_norm: boolean;
}
export interface AnalyzeRequest { photo_id: string; whole: Whole; settings?: Partial<Settings>; }
export interface QualityCheck { label: string; ok: boolean; detail: string; }
export interface PhotoResponse {
  photo_id: string; width: number; height: number;
  quality_checks: QualityCheck[]; default_whole: Whole;
}
export interface AnalyzeResponse { preview_png: string; result_token: string; }
export interface SamplePhoto { id: string; name: string; }
