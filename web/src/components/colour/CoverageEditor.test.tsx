import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { CoverageEditor } from "./CoverageEditor";
import { useProjectStore } from "../../store/projectStore";
import type { PhotoResponse } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);

describe("CoverageEditor", () => {
  beforeEach(() => {
    reset();
    useProjectStore.getState().initFromPhoto(photo());
  });

  it("renders n-1 sliders for n bands", () => {
    render(<MantineProvider><CoverageEditor g={0} n={3} coverage={[0.5, 0.3, 0.2]} /></MantineProvider>);
    const sliders = screen.getAllByRole("slider");
    expect(sliders).toHaveLength(2);
  });

  it("Reset button dispatches default coverage", () => {
    const spy = vi.spyOn(useProjectStore.getState(), "setCoverage");
    render(<MantineProvider><CoverageEditor g={0} n={3} coverage={[0.5, 0.3, 0.2]} /></MantineProvider>);
    fireEvent.click(screen.getByText("colour.reset_coverage"));
    expect(spy).toHaveBeenCalled();
  });
});
