import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { RecipeLoader } from "./RecipeLoader";
import { useProjectStore } from "../../store/projectStore";
import type { PhotoResponse } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("../../store/catalogStore", () => ({ useCatalogStore: (sel: any) => sel({ paints: [] }) }));
vi.mock("../../api/client", () => ({
  listRecipes: () => Promise.resolve({ recipes: [
    { name: "R1", steps: [{ hex: "#010101", paint_ref: null }, { hex: "#020202", paint_ref: null }, { hex: "#030303", paint_ref: null }] },
  ] }),
}));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);
const wholeHex0 = () => useProjectStore.getState().angles[0].book.whole.palette[0].hex;

describe("RecipeLoader Load→preview→Apply", () => {
  beforeEach(() => { reset(); useProjectStore.getState().initFromPhoto(photo()); });

  it("Preview does not mutate; Apply replaces the region palette", async () => {
    render(<MantineProvider><RecipeLoader onRecipeLoaded={() => {}} /></MantineProvider>);
    await waitFor(() => screen.getByText("colour.preview_recipe"));
    fireEvent.click(screen.getByText("colour.preview_recipe"));
    expect(wholeHex0()).toBe("#111");                       // preview: no mutation
    fireEvent.click(screen.getByText("colour.apply_recipe"));
    await waitFor(() => expect(wholeHex0()).toBe("#010101")); // apply: replaced
    expect(useProjectStore.getState().undoSnapshot).not.toBeNull();
  });

  it("Cancel after preview leaves the palette untouched", async () => {
    render(<MantineProvider><RecipeLoader onRecipeLoaded={() => {}} /></MantineProvider>);
    await waitFor(() => screen.getByText("colour.preview_recipe"));
    fireEvent.click(screen.getByText("colour.preview_recipe"));
    fireEvent.click(screen.getByText("colour.cancel"));
    expect(wholeHex0()).toBe("#111");
  });
});
