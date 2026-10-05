import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { BandCard, matchPhrase } from "./BandCard";
import type { PaintColor } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
const { owned } = vi.hoisted(() => ({ owned: { codes: new Set<string>() } }));
vi.mock("../../store/catalogStore", () => ({ useCatalogStore: (sel: any) => sel({ paints: [], ownedCodes: owned.codes }) }));
const { matchPaint } = vi.hoisted(() => ({ matchPaint: vi.fn() }));
vi.mock("../../api/client", () => ({ matchPaint, generateRamp: vi.fn() }));
const { removeBand, snapshotUndo, setPaletteSlot } = vi.hoisted(() => ({ removeBand: vi.fn(), snapshotUndo: vi.fn(), setPaletteSlot: vi.fn() }));
vi.mock("../../store/projectStore", () => ({
  useProjectStore: (sel: any) => sel({
    setPaletteSlot, setHexSlot: () => {}, setBandCount: () => {},
    removeBand, snapshotUndo,
  }),
}));

const paint = (): PaintColor => ({ name: "band", hex: "#808080", code: "AK1" });

function renderCard(over: Partial<React.ComponentProps<typeof BandCard>> = {}) {
  const props = {
    g: 0, i: 1, paint: paint(), finish: "matte", n: 4,
    palette: [paint(), paint(), paint(), paint()], role: "Base",
    coverageValue: 0.27, isAuto: false, onCoverage: () => {},
    ...over,
  } as React.ComponentProps<typeof BandCard>;
  return render(<MantineProvider><BandCard {...props} /></MantineProvider>);
}

describe("BandCard", () => {
  it("shows the role name", () => {
    renderCard({ role: "Midtone" });
    expect(screen.getByText("Midtone")).toBeTruthy();
  });

  it("interior band renders a coverage slider", () => {
    renderCard({ isAuto: false });
    expect(screen.getAllByRole("slider").length).toBe(1);
  });

  it("auto (top) band renders a chip, not a slider", () => {
    renderCard({ isAuto: true, role: "Highlight", coverageValue: 0.13 });
    expect(screen.queryByRole("slider")).toBeNull();
    expect(screen.getByText(/auto/i)).toBeTruthy();
  });

  it("remove is disabled at the 3-band floor", () => {
    renderCard({ n: 3 });
    expect((screen.getByLabelText("colour.delete_band") as HTMLButtonElement).disabled).toBe(true);
  });

  it("✕ removes its own band index (with an undo snapshot)", () => {
    renderCard({ i: 1, n: 4 });
    fireEvent.click(screen.getByLabelText("colour.delete_band"));
    expect(snapshotUndo).toHaveBeenCalled();
    expect(removeBand).toHaveBeenCalledWith(1);
  });

  it("the last layer shows its share as '· fills the rest'", () => {
    renderCard({ isAuto: true, role: "Highlight", coverageValue: 0.13 });
    expect(screen.getByText("13% · colour.auto")).toBeTruthy();
  });

  it("custom band asks the matcher with the owned collection and offers the closest paints", async () => {
    owned.codes = new Set(["70957"]);
    const flatRed = { name: "Flat Red", hex: "#a01c1c", brand: "Vallejo", code: "70957", finish: "matte" };
    matchPaint.mockResolvedValue({ tier: "close", phrase: "", name: "Flat Red", delta_e: 3, nearest: [
      { ...flatRed, delta_e: 3, owned: true },
    ] });
    renderCard({ paint: { name: "custom", hex: "#a51e1e", code: "" } });
    await waitFor(() => expect(matchPaint).toHaveBeenCalled(), { timeout: 2000 });
    expect(matchPaint.mock.calls[0][0].owned_codes).toEqual(["70957"]);
    await screen.findByText("≈ Flat Red");
    fireEvent.click(screen.getByLabelText("colour.which_paint"));
    fireEvent.click(await screen.findByText("colour.use_paint"));
    expect(setPaletteSlot).toHaveBeenCalledWith(0, 1, flatRed);
    owned.codes = new Set();
  });
});

describe("matchPhrase", () => {
  const t = ((k: string, o?: any) => (o ? `${k}:${o.name}` : k)) as any;
  const r = { tier: "unreachable", phrase: "", delta_e: 20, nearest: [{ name: "Ivory" }] } as any;
  it("without a collection, names the closest catalogue paint", () => {
    expect(matchPhrase(r, false, t)).toBe("colour.closest:Ivory");
  });
  it("with a collection but no mix, says it can't be mixed", () => {
    expect(matchPhrase(r, true, t)).toBe("colour.cant_mix:Ivory");
  });
  it("shows the mix recipe when one exists", () => {
    expect(matchPhrase({ ...r, tier: "mix", phrase: "Mix 1:1 A + B (approx)." }, true, t)).toBe("Mix 1:1 A + B (approx).");
  });
});
