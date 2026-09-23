import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { GeneratePanel } from "./GeneratePanel";
import { useProjectStore } from "../../store/projectStore";
import type { PhotoResponse } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("../../store/catalogStore", () => ({ useCatalogStore: (sel: any) => sel({ paints: [] }) }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);

describe("GeneratePanel", () => {
  beforeEach(() => { reset(); useProjectStore.getState().initFromPhoto(photo()); });

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
});
