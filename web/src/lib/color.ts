import type { PaintColor } from "../api/types";

export function validHex(value: string | undefined | null): string | null {
  if (!value) return null;
  const hex = value.trim().replace(/^#/, "").toLowerCase();
  if (/^[0-9a-f]{3}$/.test(hex)) return `#${hex.split("").map((c) => c + c).join("")}`;
  if (/^[0-9a-f]{6}$/.test(hex)) return `#${hex}`;
  return null;
}

export function paletteHasValidHexes(palette: PaintColor[]): boolean {
  return palette.every((paint) => validHex(paint.hex));
}