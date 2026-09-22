import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { BandEditor } from "./BandEditor";
import { useProjectStore } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import * as client from "../../api/client";
import type { PhotoResponse } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./BandSlot", () => ({ BandSlot: ({ i }: { i: number }) => <div>slot-{i}</div> }));
vi.mock("./CoverageEditor", () => ({ CoverageEditor: () => <div>coverage</div> }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: {
    palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }],
    coverage: [0.6, 0.4], material: "matte",
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

  it("renders one BandSlot per palette entry", () => {
    render(<BandEditor />);
    expect(screen.getByText("slot-0")).toBeTruthy();
    expect(screen.getByText("slot-1")).toBeTruthy();
  });
});
