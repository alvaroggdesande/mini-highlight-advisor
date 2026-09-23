import { describe, it, expect } from "vitest";
import { appendPoint } from "./RegionCanvas";

describe("live stroke reducer", () => {
  it("appendPoint accumulates points during a drag", () => {
    let s: number[][] = [];
    s = appendPoint(s, [0, 0]);
    s = appendPoint(s, [1, 1]);
    s = appendPoint(s, [2, 2]);
    expect(s).toEqual([[0, 0], [1, 1], [2, 2]]);
  });
});
