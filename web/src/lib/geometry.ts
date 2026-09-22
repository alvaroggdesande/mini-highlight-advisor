export type Pt = [number, number];

// Values mirror ui/geometry.py REGION_COLORS / REGION_EMOJIS (order = book index 1..N).
export const REGION_COLORS: string[] = ["#b432ff", "#3264ff", "#fad21e", "#32c832", "#ff3c3c"];
export const REGION_EMOJIS: string[] = ["🟣", "🔵", "🟡", "🟢", "🔴"];
export const WHOLE_MINI_EMOJI = "⬜";

export function displaySize(srcW: number, srcH: number): { dispW: number; dispH: number } {
  const dispW = Math.min(600, srcW);
  const dispH = Math.round((srcH * dispW) / srcW);
  return { dispW, dispH };
}

export function toImageSpace(pt: Pt, srcW: number, srcH: number, dispW: number, dispH: number): Pt {
  return [pt[0] * (srcW / dispW), pt[1] * (srcH / dispH)];
}

export function toDisplaySpace(pt: Pt, srcW: number, srcH: number, dispW: number, dispH: number): Pt {
  return [pt[0] * (dispW / srcW), pt[1] * (dispH / srcH)];
}

function perpDist(p: Pt, a: Pt, b: Pt): number {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const len = Math.hypot(dx, dy) || 1e-9;
  return Math.abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / len;
}

export function decimate(points: Pt[], epsilon: number): Pt[] {
  if (points.length < 3) return points.slice();
  let maxD = 0, idx = 0;
  const a = points[0], b = points[points.length - 1];
  for (let i = 1; i < points.length - 1; i++) {
    const d = perpDist(points[i], a, b);
    if (d > maxD) { maxD = d; idx = i; }
  }
  if (maxD <= epsilon) return [a, b];
  const left = decimate(points.slice(0, idx + 1), epsilon);
  const right = decimate(points.slice(idx), epsilon);
  return left.slice(0, -1).concat(right);
}

export function regionLabel(g: number, name: string): string {
  if (g === 0) return `${WHOLE_MINI_EMOJI} ${name}`;
  return `${REGION_EMOJIS[(g - 1) % REGION_EMOJIS.length]} ${name}`;
}
