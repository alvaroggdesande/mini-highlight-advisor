import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { BandSlot } from "./BandSlot";
import { useCatalogStore } from "../../store/catalogStore";
import * as client from "../../api/client";
import type { PaintColor } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));

const catalogPaint: PaintColor = { name: "Red", hex: "#ff0000", code: "R1", finish: "matte" };
const customPaint: PaintColor = { name: "custom", hex: "#aabbcc", code: "", finish: "matte" };

beforeEach(() => {
  useCatalogStore.setState({ paints: [catalogPaint], status: "ready" });
  vi.restoreAllMocks();
});

describe("BandSlot", () => {
  it("shows catalog selectbox when paint has code", () => {
    render(<BandSlot g={0} i={0} paint={catalogPaint} finish="matte" n={3} palette={[catalogPaint, catalogPaint, catalogPaint]} />);
    expect(screen.getByRole("combobox")).toBeTruthy();
  });

  it("shows colour picker when paint has no code (custom mode)", () => {
    render(<BandSlot g={0} i={0} paint={customPaint} finish="matte" n={3} palette={[customPaint, customPaint, customPaint]} />);
    const inputs = screen.getAllByRole("textbox");
    expect(inputs.length).toBeGreaterThan(0);
  });

  it("fires matchPaint debounced when in custom mode", async () => {
    const spy = vi.spyOn(client, "matchPaint").mockResolvedValue({
      tier: "close", phrase: "Closest: Red", name: "Red", hex: "#ff0000", delta_e: 3,
    });
    vi.useFakeTimers();
    render(<BandSlot g={0} i={0} paint={customPaint} finish="matte" n={3} palette={[customPaint, customPaint, customPaint]} />);
    await act(async () => { vi.advanceTimersByTime(500); });
    expect(spy).toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("delete button is disabled when n=3", () => {
    render(<BandSlot g={0} i={0} paint={catalogPaint} finish="matte" n={3} palette={[catalogPaint, catalogPaint, catalogPaint]} />);
    const del = screen.getByTitle("colour.delete_band");
    expect((del as HTMLButtonElement).disabled).toBe(true);
  });
});
