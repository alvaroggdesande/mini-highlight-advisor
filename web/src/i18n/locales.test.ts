import { it, expect } from "vitest";
import en from "./locales/en.json";
import es from "./locales/es.json";

function keys(o: any, p = ""): string[] {
  return Object.entries(o).flatMap(([k, v]) =>
    v && typeof v === "object" ? keys(v, `${p}${k}.`) : [`${p}${k}`]);
}

it("en and es have identical key sets", () => {
  expect(keys(es).sort()).toEqual(keys(en).sort());
});

it("no locale value contains markdown headings", () => {
  for (const v of [...keys(en).map((k) => k.split(".").reduce((o: any, s) => o[s], en)),
                   ...keys(es).map((k) => k.split(".").reduce((o: any, s) => o[s], es))]) {
    expect(String(v).startsWith("#")).toBe(false);
  }
});

it("no developer jargon (L2/L3, N2/N3, 'auto') in locale values", () => {
  for (const loc of [en, es]) {
    for (const k of keys(loc)) {
      const v = String(k.split(".").reduce((o: any, s) => o[s], loc));
      expect(v, k).not.toMatch(/\((L|N)[123]\)/);
      expect(v, k).not.toMatch(/^auto$/);
    }
  }
});

it("has the Studio step keys", () => {
  for (const k of ["studio.step_regions", "studio.step_scheme", "studio.step_layers",
                   "studio.save_share", "edges.enabled", "studio.fill_from"]) {
    expect(keys(en)).toContain(k);
  }
});
