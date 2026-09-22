import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { useProjectStore } from "../store/projectStore";

vi.mock("react-konva", () => {
  const Passthrough = ({ children }: any) => <div>{children}</div>;
  return { Stage: Passthrough, Layer: Passthrough, Line: () => <div data-testid="konva-line" />,
           Image: () => <div data-testid="konva-image" /> };
});
vi.mock("use-image", () => ({ default: () => [null] }));

import { RegionCanvas } from "./RegionCanvas";

const photo = (id = "p1") => ({ photo_id: id, width: 200, height: 100, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#000" }], coverage: [1], material: "matte" } });

describe("RegionCanvas", () => {
  beforeEach(() => useProjectStore.setState(useProjectStore.getInitialState(), true));

  it("renders one konva Line per existing drawn region ring", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo());
    st.addRegion([[[10, 10], [20, 10], [20, 20]]], "helmet");
    render(<RegionCanvas drawing={false} draftRings={[]} onDraftChange={() => {}} />);
    expect(screen.getAllByTestId("konva-line").length).toBeGreaterThanOrEqual(1);
  });
});
