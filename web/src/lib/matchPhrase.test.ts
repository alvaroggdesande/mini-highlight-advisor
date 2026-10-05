import { describe, it, expect } from "vitest";
import { matchPhrase } from "./matchPhrase";

describe("matchPhrase", () => {
  const t = ((k: string, o?: Record<string, string>) => (o ? `${k}:${Object.values(o).join("|")}` : k)) as any;
  const r = { tier: "unreachable", phrase: "", delta_e: 20, nearest: [{ name: "Ivory" }] } as any;
  it("without a collection, names the closest catalogue paint", () => {
    expect(matchPhrase(r, false, t)).toBe("colour.closest:Ivory");
  });
  it("with a collection but no mix, says it can't be mixed", () => {
    expect(matchPhrase(r, true, t)).toBe("colour.cant_mix:Ivory");
  });
  it("phrases a mix through i18n from the structured recipe", () => {
    const mix = { ...r, tier: "mix", phrase: "Mix 1:2 A + B (approx).", mix: { parts: [1, 2], names: ["A", "B"], tint: false } };
    expect(matchPhrase(mix, true, t)).toBe("colour.mix:1:2|A + B");
  });
  it("phrases a metallic tint mix with its own string", () => {
    const mix = { ...r, tier: "mix", phrase: "", mix: { parts: [3, 1], names: ["Gold", "Red"], tint: true } };
    expect(matchPhrase(mix, true, t)).toBe("colour.mix_tint:3:1|Gold|Red");
  });
  it("falls back to the backend phrase when no structured recipe is sent", () => {
    expect(matchPhrase({ ...r, tier: "mix", phrase: "Mix 1:1 A + B (approx)." }, true, t)).toBe("Mix 1:1 A + B (approx).");
  });
  it("names the brand next to every paint", () => {
    const close = { tier: "close", phrase: "", name: "Flat Red", brand: "Vallejo", delta_e: 3, nearest: [] } as any;
    expect(matchPhrase(close, true, t)).toBe("≈ Flat Red (Vallejo)");
    const mix = { ...r, tier: "mix", mix: { parts: [1, 1], names: ["A", "B"], brands: ["Citadel", "Vallejo"], tint: false } };
    expect(matchPhrase(mix, true, t)).toBe("colour.mix:1:1|A (Citadel) + B (Vallejo)");
    expect(matchPhrase({ ...r, nearest: [{ name: "Ivory", brand: "AK Interactive" }] }, false, t))
      .toBe("colour.closest:Ivory (AK Interactive)");
  });
});
