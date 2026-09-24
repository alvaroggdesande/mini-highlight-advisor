import { describe, expect, it } from "vitest";
import { paletteHasValidHexes, validHex } from "./color";

describe("color helpers", () => {
  it("normalizes valid css hex colors", () => {
    expect(validHex("#ABC")).toBe("#aabbcc");
    expect(validHex("112233")).toBe("#112233");
  });

  it("rejects blank and incomplete colors", () => {
    expect(validHex("")).toBeNull();
    expect(validHex("#12")).toBeNull();
    expect(validHex("#zzzzzz")).toBeNull();
  });

  it("detects invalid palette entries", () => {
    expect(paletteHasValidHexes([{ name: "a", hex: "#111111" }, { name: "b", hex: "" }])).toBe(false);
  });
});