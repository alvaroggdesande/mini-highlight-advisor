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
