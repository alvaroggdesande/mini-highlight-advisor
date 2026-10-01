import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { StudioPanel } from "./StudioPanel";
import { useProjectStore } from "../store/projectStore";
import type { PhotoResponse } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
// RegionCanvas uses react-konva (canvas) which jsdom cannot render — stub it.
vi.mock("./RegionCanvas", () => ({ RegionCanvas: () => null }));
vi.mock("./colour/RecipeLoader", () => ({ RecipeLoader: () => null }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);

describe("StudioPanel", () => {
  beforeEach(() => { reset(); useProjectStore.getState().initFromPhoto(photo()); });

  it("renders a sticky preview column and an editor column", () => {
    render(<MantineProvider><StudioPanel onGoToPaint={() => {}} /></MantineProvider>);
    const preview = screen.getByTestId("studio-preview");
    expect(preview).toBeTruthy();
    expect(preview.style.position).toBe("sticky");
    expect(screen.getByTestId("studio-editor")).toBeTruthy();
  });

  it("'see painting steps' is disabled until the first result, then calls onGoToPaint", () => {
    const go = vi.fn();
    const { rerender } = render(<MantineProvider><StudioPanel onGoToPaint={go} /></MantineProvider>);
    const btn = () => screen.getByRole("button", { name: "studio.go_to_paint" });
    expect(btn()).toBeDisabled();
    const s = useProjectStore.getState();
    useProjectStore.setState({ angles: s.angles.map((a, i) => i === 0 ? { ...a, resultToken: "tok" } : a) });
    rerender(<MantineProvider><StudioPanel onGoToPaint={go} /></MantineProvider>);
    fireEvent.click(btn());
    expect(go).toHaveBeenCalledOnce();
  });

  it("shows the photo-quality alert when a check fails", () => {
    reset();
    useProjectStore.getState().initFromPhoto({ ...photo(), quality_checks: [{ id: "focus", label: "Focus", ok: false, detail: "x" }] });
    render(<MantineProvider><StudioPanel onGoToPaint={() => {}} /></MantineProvider>);
    expect(screen.getByText("quality.title")).toBeTruthy();
  });

  it("shows the steps in order: regions → colour scheme → layers → save & share", () => {
    render(<MantineProvider><StudioPanel onGoToPaint={() => {}} /></MantineProvider>);
    const order = ["step-regions", "step-scheme", "step-layers", "save-share"].map((id) => screen.getByTestId(id));
    for (let i = 1; i < order.length; i++) {
      expect(order[i - 1].compareDocumentPosition(order[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
  });
});
