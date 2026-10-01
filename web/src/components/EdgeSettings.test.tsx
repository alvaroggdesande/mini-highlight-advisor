import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { EdgeSettings } from "./EdgeSettings";
import { useProjectStore, activeAngleOf } from "../store/projectStore";
import type { PhotoResponse } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);
const settings = () => activeAngleOf(useProjectStore.getState())!.settings;
const ui = () => render(<MantineProvider><EdgeSettings /></MantineProvider>);

describe("EdgeSettings", () => {
  beforeEach(() => { reset(); useProjectStore.getState().initFromPhoto(photo()); });

  it("checkboxes write edge_hl and edge_extreme", () => {
    ui();
    fireEvent.click(screen.getByLabelText("edges.extreme"));
    expect(settings().edge_extreme).toBe(true);
    fireEvent.click(screen.getByLabelText("edges.enabled"));
    expect(settings().edge_hl).toBe(false);
  });

  it("turning edge highlights off disables extra-sharp and the slider", () => {
    useProjectStore.getState().setSettings({ edge_hl: false });
    ui();
    expect(screen.getByLabelText("edges.extreme")).toBeDisabled();
    expect(screen.getByRole("slider", { name: "edges.sens" }).hasAttribute("data-disabled")).toBe(true);
  });

  it("the edge slider commits edge_sens", () => {
    ui();
    const thumb = screen.getByRole("slider", { name: "edges.sens" });
    fireEvent.keyDown(thumb, { key: "ArrowRight" });
    expect(settings().edge_sens).toBeCloseTo(0.55);
  });
});
