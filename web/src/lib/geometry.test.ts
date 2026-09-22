import { describe, it, expect } from "vitest";
import { displaySize, toImageSpace, toDisplaySpace, decimate, regionLabel, REGION_EMOJIS } from "./geometry";

describe("geometry", () => {
  it("displaySize caps width at 600 and preserves aspect", () => {
    expect(displaySize(1200, 900)).toEqual({ dispW: 600, dispH: 450 });
    expect(displaySize(400, 800)).toEqual({ dispW: 400, dispH: 800 });
  });

  it("toImageSpace scales display point to source pixels (matches scale_points)", () => {
    const { dispW, dispH } = displaySize(1200, 900); // 600x450, sx=sy=2
    expect(toImageSpace([100, 50], 1200, 900, dispW, dispH)).toEqual([200, 100]);
  });

  it("toImageSpace -> toDisplaySpace round-trips", () => {
    const { dispW, dispH } = displaySize(1200, 900);
    const img = toImageSpace([123, 77], 1200, 900, dispW, dispH);
    const back = toDisplaySpace(img, 1200, 900, dispW, dispH);
    expect(back[0]).toBeCloseTo(123);
    expect(back[1]).toBeCloseTo(77);
  });

  it("decimate drops collinear points but keeps endpoints and corners", () => {
    const line: [number, number][] = [[0, 0], [1, 0], [2, 0], [3, 0], [3, 3]];
    const out = decimate(line, 0.5);
    expect(out).toContainEqual([0, 0]);
    expect(out).toContainEqual([3, 0]);
    expect(out).toContainEqual([3, 3]);
    expect(out.length).toBeLessThan(line.length);
  });

  it("regionLabel prefixes the region emoji cycling by index", () => {
    expect(regionLabel(1, "helmet")).toBe(`${REGION_EMOJIS[0]} helmet`);
  });
});
