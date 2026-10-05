import type { TFunction } from "i18next";
import type { MatchResult } from "../api/types";

/** One-line guide for a custom colour: how to get it from YOUR paints. */
export function matchPhrase(r: MatchResult, hasOwned: boolean, t: TFunction): string {
  const closest = r.nearest[0]?.name ?? "";
  if (!hasOwned) return t("colour.closest", { name: closest });
  if (r.tier === "exact") return `✓ ${r.name ?? ""}`;
  if (r.tier === "close") return `≈ ${r.name ?? ""}`;
  if (r.tier === "mix") {
    if (!r.mix) return r.phrase;
    const ratio = r.mix.parts.join(":");
    if (r.mix.tint) return t("colour.mix_tint", { ratio, metal: r.mix.names[0], tint: r.mix.names[1] });
    return t("colour.mix", { ratio, names: r.mix.names.join(" + ") });
  }
  return t("colour.cant_mix", { name: closest });
}
