import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { RampEditor } from "./RampEditor";

const ivory = { name: "Ivory", hex: "#f0e6c8", brand: "Vallejo", code: "70918", finish: "matte" };
vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("../../store/catalogStore", () => ({ useCatalogStore: (sel: any) => sel({ paints: [ivory] }) }));
const { setHexSlot, setPaletteSlot, setRampState, generateRamp } = vi.hoisted(() => ({
  setHexSlot: vi.fn(), setPaletteSlot: vi.fn(), setRampState: vi.fn(), generateRamp: vi.fn(),
}));
vi.mock("../../api/client", () => ({ generateRamp }));
const grey = { name: "custom", hex: "#808080", code: "" };
const book = { selected: 0, hero_hex: null, drawn: [], whole: { palette: [grey, grey, grey, grey, grey] } };
vi.mock("../../store/projectStore", () => ({
  activeBookOf: () => book,
  useProjectStore: (sel: any) => sel({ setHexSlot, setPaletteSlot, setRampState }),
}));

function pickIvory() {
  render(<MantineProvider><RampEditor /></MantineProvider>);
  const input = screen.getByPlaceholderText("colour.search_paint");
  fireEvent.click(input);
  fireEvent.change(input, { target: { value: "ivory" } });
  fireEvent.click(screen.getByText("Ivory"));
}

describe("RampEditor", () => {
  it("keeps the picked paint shown and makes it the middle layer of a plain ramp", async () => {
    generateRamp.mockResolvedValue({ hexes: ["#111111", "#555555", "#f0e6c8", "#f5f0e0", "#ffffff"] });
    pickIvory();
    expect((screen.getByPlaceholderText("colour.search_paint") as HTMLInputElement).value).toContain("Ivory");
    fireEvent.click(screen.getByText("colour.ramp"));
    await waitFor(() => expect(setPaletteSlot).toHaveBeenCalledWith(0, 2, ivory));
    expect(generateRamp).toHaveBeenCalledWith({ midtone_hex: "#f0e6c8", n: 5, variant: "ramp" });
  });

  it("hue-shifted variants don't claim the middle layer is the picked paint", async () => {
    setPaletteSlot.mockClear();
    generateRamp.mockResolvedValue({ hexes: ["#111111", "#222222", "#333333", "#444444", "#555555"] });
    pickIvory();
    fireEvent.click(screen.getByText("colour.complementary"));
    await waitFor(() => expect(setRampState).toHaveBeenCalled());
    expect(setPaletteSlot).not.toHaveBeenCalled();
  });
});
