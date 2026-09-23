import { describe, it, expect } from "vitest";
import { roleNames, defaultCoverage } from "./roles";

describe("roles", () => {
  it("names the 4-band roles", () => {
    expect(roleNames(4)).toEqual(["Shadow", "Base", "Midtone", "Highlight"]);
  });
  it("falls back to Layer N outside 3-7", () => {
    expect(roleNames(2)).toEqual(["Layer 1", "Layer 2"]);
  });
  it("defaultCoverage sums to 1 and descends", () => {
    const cov = defaultCoverage(4);
    expect(cov[0]).toBeGreaterThan(cov[3]);
    expect(cov.reduce((a, b) => a + b, 0)).toBeCloseTo(1, 6);
  });
});
