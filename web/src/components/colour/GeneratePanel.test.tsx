import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import * as client from "../../api/client";
import { MantineProvider } from "@mantine/core";
import { GeneratePanel } from "./GeneratePanel";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import type { PhotoResponse } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
const cat = vi.hoisted(() => ({ paints: [] as any[], ownedCodes: new Set<string>() }));
vi.mock("../../store/catalogStore", () => ({ useCatalogStore: (sel: any) => sel(cat) }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);

describe("GeneratePanel", () => {
  beforeEach(() => {
    reset(); useProjectStore.getState().initFromPhoto(photo());
    cat.paints = [{ code: "V1" }, { code: "V2" }] as any; cat.ownedCodes = new Set(["V1"]);
    vi.restoreAllMocks();
  });

  it("is expanded (Generate button visible) when no scheme has been generated", () => {
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    expect(screen.queryByText("colour.generate")).toBeTruthy();
  });

  it("is collapsed (Generate button hidden) once hero_hex is set", () => {
    useProjectStore.getState().setHeroHex("#c0392b");
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    expect(screen.queryByText("colour.generate")).toBeNull();
    expect(screen.getByTestId("generate-toggle")).toBeTruthy();
  });

  it("does not render a per-region surface/tone table", () => {
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    expect(screen.queryByText("colour.tone")).toBeNull();
  });

  it("owned-only sends owned codes, not the whole catalogue", async () => {
    const spy = vi.spyOn(client, "generateScheme").mockResolvedValue({ palettes: {} } as any);
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    fireEvent.click(screen.getByLabelText("colour.owned_only"));
    fireEvent.click(screen.getByText("colour.generate"));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy.mock.calls[0][0].owned_codes).toEqual(["V1"]);
    expect(spy.mock.calls[0][0].anchor_name).toBe("Whole Mini");
  });

  it("owned-only with nothing owned sends [] and shows a hint", async () => {
    cat.ownedCodes = new Set();
    const spy = vi.spyOn(client, "generateScheme").mockResolvedValue({ palettes: {} } as any);
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    fireEvent.click(screen.getByLabelText("colour.owned_only"));
    expect(screen.getByText("colour.owned_only_none")).toBeTruthy();
    fireEvent.click(screen.getByText("colour.generate"));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy.mock.calls[0][0].owned_codes).toEqual([]);
  });

  it("shows an error notice when generation fails", async () => {
    vi.spyOn(client, "generateScheme").mockRejectedValue(new Error("500 boom"));
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    fireEvent.click(screen.getByText("colour.generate"));
    expect(await screen.findByText("errors.generate")).toBeTruthy();
    expect(screen.getByText("500 boom")).toBeTruthy();
  });

  it("has no anchor dropdown and shows the ★ caption", () => {
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    expect(screen.queryByLabelText("colour.anchor_region")).toBeNull();
    expect(screen.getByText("studio.anchor_caption")).toBeTruthy();
  });

  it("anchors the request on the ★ region from the store", async () => {
    useProjectStore.getState().addRegion([[[1, 1], [2, 2], [3, 1]]], "Cloak");
    const id = activeBookOf(useProjectStore.getState())!.drawn[0].id;
    useProjectStore.getState().setAnchor(id);
    const spy = vi.spyOn(client, "generateScheme").mockResolvedValue({ palettes: {} } as any);
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    fireEvent.click(screen.getByText("colour.generate"));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    const req = spy.mock.calls[0][0];
    expect(req.anchor_name).toBe("Cloak");
    expect(req.specs.map((s) => s.is_anchor)).toEqual([false, true]);
  });

  it("an unknown anchor id falls back to Whole Mini", async () => {
    useProjectStore.getState().setAnchor("gone");
    const spy = vi.spyOn(client, "generateScheme").mockResolvedValue({ palettes: {} } as any);
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    fireEvent.click(screen.getByText("colour.generate"));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy.mock.calls[0][0].anchor_name).toBe("Whole Mini");
    expect(spy.mock.calls[0][0].specs[0].is_anchor).toBe(true);
  });
});
