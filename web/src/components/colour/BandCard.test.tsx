import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { BandCard } from "./BandCard";
import type { PaintColor } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("../../store/catalogStore", () => ({ useCatalogStore: (sel: any) => sel({ paints: [] }) }));
vi.mock("../../store/projectStore", () => ({
  useProjectStore: (sel: any) => sel({
    setPaletteSlot: () => {}, setHexSlot: () => {}, setBandCount: () => {},
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
});
