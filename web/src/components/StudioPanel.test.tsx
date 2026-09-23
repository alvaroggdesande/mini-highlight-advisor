import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
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
    render(<MantineProvider><StudioPanel /></MantineProvider>);
    const preview = screen.getByTestId("studio-preview");
    expect(preview).toBeTruthy();
    expect(preview.style.position).toBe("sticky");
    expect(screen.getByTestId("studio-editor")).toBeTruthy();
  });
});
