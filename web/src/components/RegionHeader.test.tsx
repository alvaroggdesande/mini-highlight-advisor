import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { RegionHeader } from "./RegionHeader";
import { useProjectStore } from "../store/projectStore";
import type { PhotoResponse } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./RegionCanvas", () => ({ RegionCanvas: () => null }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);

describe("RegionHeader", () => {
  beforeEach(() => {
    reset();
    useProjectStore.getState().initFromPhoto(photo());
    useProjectStore.getState().addRegion([[[1, 1], [2, 2], [3, 1]]], "Cloak");
    useProjectStore.getState().setSelected(0);
  });

  it("switching the region select calls setSelected", () => {
    render(<MantineProvider><RegionHeader /></MantineProvider>);
    const sel = screen.getByLabelText("region") as HTMLSelectElement;
    fireEvent.change(sel, { target: { value: "1" } });
    expect(useProjectStore.getState().angles[0].book.selected).toBe(1);
  });

  it("finish select updates material on the selected region", () => {
    render(<MantineProvider><RegionHeader /></MantineProvider>);
    const finish = screen.getByLabelText("technique.material") as HTMLSelectElement;
    fireEvent.change(finish, { target: { value: "metallic" } });
    expect(useProjectStore.getState().angles[0].book.whole.material).toBe("metallic");
  });
});
