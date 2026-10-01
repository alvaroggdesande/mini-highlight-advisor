import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { RegionTable } from "./RegionTable";
import { useProjectStore, activeBookOf } from "../store/projectStore";
import type { PhotoResponse } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./ManagePanel", () => ({ ManagePanel: () => <div>manage-panel</div> }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);
const book = () => activeBookOf(useProjectStore.getState())!;
const ui = () => render(<MantineProvider><RegionTable /></MantineProvider>);

describe("RegionTable", () => {
  beforeEach(() => {
    reset();
    useProjectStore.getState().initFromPhoto(photo());
    useProjectStore.getState().addRegion([[[1, 1], [2, 2], [3, 1]]], "Cloak");
    useProjectStore.getState().setSelected(0);
  });

  it("renders one row per region, whole mini first", () => {
    ui();
    expect(screen.getByTestId("region-row-0").textContent).toContain("region.whole_mini");
    expect(screen.getByTestId("region-row-1").textContent).toContain("Cloak");
  });

  it("clicking a row selects it and marks it aria-selected", () => {
    const { rerender } = ui();
    fireEvent.click(screen.getByText("Cloak"));
    expect(book().selected).toBe(1);
    rerender(<MantineProvider><RegionTable /></MantineProvider>);
    expect(screen.getByTestId("region-row-1").getAttribute("aria-selected")).toBe("true");
    expect(screen.getByTestId("region-row-0").getAttribute("aria-selected")).toBe("false");
  });

  it("editing a non-selected row updates that row without changing the selection", () => {
    ui();
    fireEvent.change(screen.getByLabelText("technique.material Cloak"), { target: { value: "metallic" } });
    fireEvent.change(screen.getByLabelText("colour.tone Cloak"), { target: { value: "dark" } });
    expect(book().drawn[0].material).toBe("metallic");
    expect(book().drawn[0].tone).toBe("dark");
    expect(book().whole.material).toBe("matte");
    expect(book().selected).toBe(0);
  });

  it("★ starts on whole mini and moves to the clicked row without selecting it", () => {
    const { rerender } = ui();
    const stars = () => screen.getAllByLabelText("studio.anchor_aria");
    expect(stars()[0].textContent).toBe("★");
    expect(stars()[1].textContent).toBe("☆");
    fireEvent.click(stars()[1]);
    expect(book().anchor_id).toBe(book().drawn[0].id);
    expect(book().selected).toBe(0);
    rerender(<MantineProvider><RegionTable /></MantineProvider>);
    expect(stars()[1].textContent).toBe("★");
  });

  it("deleting the starred region puts the ★ back on whole mini", () => {
    useProjectStore.getState().setAnchor(book().drawn[0].id);
    useProjectStore.getState().removeRegion(1);
    ui();
    expect(screen.getAllByLabelText("studio.anchor_aria")[0].textContent).toBe("★");
  });

  it("'Draw a region' toggles the region manager", () => {
    ui();
    const btn = screen.getByRole("button", { name: "studio.draw_region" });
    expect(btn.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("manage-panel")).toBeTruthy();
  });
});
