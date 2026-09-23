import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { BandEditor } from "./BandEditor";
import { useProjectStore } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import * as client from "../../api/client";
import type { PhotoResponse } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./BandCard", () => ({ BandCard: ({ role }: { role: string }) => <div>card-{role}</div> }));
vi.mock("./RecipeFooter", () => ({ RecipeFooter: () => <div>footer</div> }));

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
    expect(screen.getByText("card-Shadow")).toBeTruthy();
    expect(screen.getByText("card-Base")).toBeTruthy();
    expect(screen.getByText("card-Highlight")).toBeTruthy();
  });

  it("renders the RecipeFooter", () => {
    render(<MantineProvider><BandEditor /></MantineProvider>);
    expect(screen.getByText("footer")).toBeTruthy();
  });
});
