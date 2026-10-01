import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { LayerTools } from "./LayerTools";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import type { PhotoResponse } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./RampEditor", () => ({ RampEditor: () => <div>ramp-editor</div> }));
vi.mock("./RecipeLoader", () => ({ RecipeLoader: () => <div>recipe-loader</div> }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);
const ui = (n = 3) => render(<MantineProvider><LayerTools g={0} n={n} onRecipeChanged={() => {}} /></MantineProvider>);

describe("LayerTools", () => {
  beforeEach(() => { reset(); useProjectStore.getState().initFromPhoto(photo()); });

  it("undo button's accessible name is translated", () => {
    ui();
    expect(screen.getByLabelText("colour.undo")).toBeTruthy();
  });

  it("Add layer appends a layer, and is disabled at 7", () => {
    const { unmount } = ui(3);
    fireEvent.click(screen.getByText("colour.add_band"));
    expect(activeBookOf(useProjectStore.getState())!.whole.palette).toHaveLength(4);
    unmount();
    ui(7);
    expect(screen.getByText("colour.add_band").closest("button")).toBeDisabled();
  });

  it("fill tools open one panel at a time and close on second click", () => {
    ui();
    expect(screen.queryByText("ramp-editor")).toBeNull();
    expect(screen.queryByText("recipe-loader")).toBeNull();
    fireEvent.click(screen.getByText("studio.fill_one_colour"));
    expect(screen.getByText("ramp-editor")).toBeTruthy();
    fireEvent.click(screen.getByText("studio.fill_recipe"));
    expect(screen.queryByText("ramp-editor")).toBeNull();
    expect(screen.getByText("recipe-loader")).toBeTruthy();
    fireEvent.click(screen.getByText("studio.fill_recipe"));
    expect(screen.queryByText("recipe-loader")).toBeNull();
  });
});
