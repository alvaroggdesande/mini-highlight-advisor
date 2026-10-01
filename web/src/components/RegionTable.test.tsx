import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { RegionTable } from "./RegionTable";
import { useProjectStore, activeBookOf } from "../store/projectStore";
import type { PhotoResponse } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./ManagePanel", () => ({
  ManagePanel: ({ onClose }: any) => <button onClick={onClose}>manage-panel</button>,
}));

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
    expect(screen.getByLabelText("region.name_aria")).toHaveProperty("value", "Cloak");
  });

  it("clicking a row selects it and marks it aria-selected", () => {
    const { rerender } = ui();
    fireEvent.click(screen.getByTestId("region-row-1"));
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

  it("'Draw a region' opens the drawing panel and relabels itself to hide it", () => {
    ui();
    const btn = screen.getByRole("button", { name: /studio.draw_region/ });
    expect(btn.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("manage-panel")).toBeNull();
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-expanded")).toBe("true");
    expect(btn.textContent).toContain("studio.hide_drawing");
    expect(screen.getByText("manage-panel")).toBeTruthy();
    fireEvent.click(btn);
    expect(screen.queryByText("manage-panel")).toBeNull();
  });

  it("drawing panel closes itself when it finishes (Add/Cancel)", () => {
    ui();
    fireEvent.click(screen.getByRole("button", { name: /studio.draw_region/ }));
    fireEvent.click(screen.getByText("manage-panel"));   // mock calls onClose
    expect(screen.queryByText("manage-panel")).toBeNull();
    expect(screen.getByRole("button", { name: /studio.draw_region/ }).getAttribute("aria-expanded")).toBe("false");
  });

  it("renaming a drawn region in its row", () => {
    ui();
    fireEvent.change(screen.getByLabelText("region.name_aria"), { target: { value: "Cape" } });
    expect(book().drawn[0].name).toBe("Cape");
  });

  it("visible checkbox in the row toggles blank without selecting", () => {
    ui();
    const before = book().drawn[0].blank;
    fireEvent.click(screen.getByLabelText("region.visible Cloak"));
    expect(book().drawn[0].blank).toBe(!before);
    expect(book().selected).toBe(0);
  });

  it("✕ in the row deletes that region; whole mini has no ✕", () => {
    ui();
    expect(screen.getAllByRole("button", { name: /region.delete/ })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "region.delete Cloak" }));
    expect(book().drawn).toHaveLength(0);
  });

  it("shows the regions intro only while there are no drawn regions", () => {
    useProjectStore.getState().removeRegion(1);
    const { rerender } = ui();
    expect(screen.getByText("region.intro")).toBeTruthy();
    act(() => useProjectStore.getState().addRegion([[[1, 1], [2, 2], [3, 1]]], "Cloak"));
    rerender(<MantineProvider><RegionTable /></MantineProvider>);
    expect(screen.queryByText("region.intro")).toBeNull();
  });
});
