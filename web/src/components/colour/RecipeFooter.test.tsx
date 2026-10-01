import { it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { RecipeFooter } from "./RecipeFooter";
import { useProjectStore } from "../../store/projectStore";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./RampEditor", () => ({ RampEditor: () => null }));
vi.mock("./RecipeLoader", () => ({ RecipeLoader: () => null }));
vi.mock("./RecipeSaver", () => ({ RecipeSaver: () => null }));

it("undo button's accessible name is translated", () => {
  useProjectStore.getState().initFromPhoto({ photo_id: "p", width: 10, height: 10, quality_checks: [],
    default_whole: { palette: [{ name: "a", hex: "#000000" }], coverage: [1], material: "matte" } } as any);
  render(<MantineProvider><RecipeFooter g={0} n={3} onRecipeChanged={() => {}} /></MantineProvider>);
  expect(screen.getByLabelText("colour.undo")).toBeTruthy();
});
