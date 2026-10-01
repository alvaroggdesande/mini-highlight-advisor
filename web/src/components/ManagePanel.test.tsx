import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { useProjectStore } from "../store/projectStore";
import type { PhotoResponse } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./RegionCanvas", () => ({
  RegionCanvas: ({ onDraftChange }: any) => (
    <button onClick={() => onDraftChange([[[0, 0], [5, 0], [5, 5]]])}>mock-draw</button>
  ),
}));
import { ManagePanel } from "./ManagePanel";

const photo = (): PhotoResponse => ({ photo_id: "p", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#000" }], coverage: [1], material: "matte" } });

const ui = (onClose = vi.fn()) => {
  render(<MantineProvider><ManagePanel onClose={onClose} /></MantineProvider>);
  return onClose;
};

describe("ManagePanel", () => {
  beforeEach(() => {
    useProjectStore.setState(useProjectStore.getInitialState(), true);
    useProjectStore.getState().initFromPhoto(photo());
  });

  it("opens straight into drawing with the lasso hint", () => {
    ui();
    expect(screen.getByText("region.draw_hint")).toBeTruthy();
    expect(screen.getByText("region.add")).toBeTruthy();
    expect(screen.getByText("region.cancel")).toBeTruthy();
  });

  it("Add is disabled until a stroke is drawn", () => {
    ui();
    expect(screen.getByRole("button", { name: "region.add" }).hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByText("mock-draw"));
    expect(screen.getByRole("button", { name: "region.add" }).hasAttribute("disabled")).toBe(false);
  });

  it("capture stroke -> Add commits a region and closes", () => {
    const onClose = ui();
    fireEvent.click(screen.getByText("mock-draw"));
    fireEvent.click(screen.getByText("region.add"));
    expect(useProjectStore.getState().angles[0].book.drawn).toHaveLength(1);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("Cancel closes without adding a region", () => {
    const onClose = ui();
    fireEvent.click(screen.getByText("mock-draw"));
    fireEvent.click(screen.getByText("region.cancel"));
    expect(useProjectStore.getState().angles[0].book.drawn).toHaveLength(0);
    expect(onClose).toHaveBeenCalledOnce();
  });
});
