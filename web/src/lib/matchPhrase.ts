import type { TFunction } from "i18next";
import type { MatchResult } from "../api/types";

/** "Name (Brand)" — the same colour name exists in several brands. */
export function withBrand(name: string, brand?: string | null): string {
  return brand ? `${name} (${brand})` : name;
}

/** One-line guide for a custom colour: how to get it from YOUR paints. */
export function matchPhrase(r: MatchResult, hasOwned: boolean, t: TFunction): string {
  const n0 = r.nearest[0];
  const closest = n0 ? withBrand(n0.name, n0.brand) : "";
  const own = withBrand(r.name ?? "", r.brand);
  if (!hasOwned) return t("colour.closest", { name: closest });
  if (r.tier === "exact") return `✓ ${own}`;
  if (r.tier === "close") return `≈ ${own}`;
  if (r.tier === "mix") {
    if (!r.mix) return r.phrase;
    const ratio = r.mix.parts.join(":");
    const names = r.mix.names.map((n, k) => withBrand(n, r.mix!.brands?.[k]));
    if (r.mix.tint) return t("colour.mix_tint", { ratio, metal: names[0], tint: names[1] });
    return t("colour.mix", { ratio, names: names.join(" + ") });
  }
  return t("colour.cant_mix", { name: closest });
}
