import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { BandEditor } from "./BandEditor";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import * as client from "../../api/client";
import type { PhotoResponse } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./BandCard", () => ({ BandCard: ({ role }: { role: string }) => <div>card-{role}</div> }));
// Stateful stand-in: shows the g it was first mounted with, so a missing remount on region change is visible.
vi.mock("./LayerTools", async () => {
  const { useState } = await import("react");
  return { LayerTools: ({ g }: { g: number }) => { const [g0] = useState(g); return <div>layer-tools-{g0}</div>; } };
});
vi.mock("../EdgeSettings", () => ({ EdgeSettings: () => <div>edge-settings</div> }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: {
    palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
    coverage: [0.5, 0.3, 0.2], material: "matte",
  },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);

describe("BandEditor", () => {
  beforeEach(() => {
    reset();
    useProjectStore.getState().initFromPhoto(photo());
    useCatalogStore.setState({ paints: [], status: "ready" });
    vi.spyOn(client, "listRecipes").mockResolvedValue({ recipes: [] });
  });

  it("renders one BandCard per palette entry with role names", () => {
    render(<MantineProvider><BandEditor /></MantineProvider>);
    expect(screen.getByText("card-roles.shadow")).toBeTruthy();
    expect(screen.getByText("card-roles.base")).toBeTruthy();
    expect(screen.getByText("card-roles.highlight")).toBeTruthy();
  });

  it("renders the layer tools", () => {
    render(<MantineProvider><BandEditor /></MantineProvider>);
    expect(screen.getByText("layer-tools-0")).toBeTruthy();
  });

  it("the 'Layers for' picker reflects and changes the selected region", () => {
    useProjectStore.getState().addRegion([[[1, 1], [2, 2], [3, 1]]], "Cloak");   // selects 1
    render(<MantineProvider><BandEditor /></MantineProvider>);
    const sel = screen.getByLabelText("region.select") as HTMLSelectElement;
    expect(sel.value).toBe("1");
    fireEvent.change(sel, { target: { value: "0" } });
    expect(activeBookOf(useProjectStore.getState())!.selected).toBe(0);
  });

  it("switching region remounts the layer tools so an open fill panel can't target the new region", () => {
    useProjectStore.getState().addRegion([[[1, 1], [2, 2], [3, 1]]], "Cloak");   // selects 1
    useProjectStore.getState().setSelected(0);
    const { rerender } = render(<MantineProvider><BandEditor /></MantineProvider>);
    expect(screen.getByText("layer-tools-0")).toBeTruthy();
    useProjectStore.getState().setSelected(1);
    rerender(<MantineProvider><BandEditor /></MantineProvider>);
    expect(screen.getByText("layer-tools-1")).toBeTruthy();
  });
});
