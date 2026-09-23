import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { useProjectStore } from "../store/projectStore";

vi.mock("./RegionCanvas", () => ({
  RegionCanvas: ({ onDraftChange }: any) => (
    <button onClick={() => onDraftChange([[[0, 0], [5, 0], [5, 5]]])}>mock-draw</button>
  ),
}));
import { ManagePanel } from "./ManagePanel";

const photo = () => ({ photo_id: "p", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#000" }], coverage: [1], material: "matte" } });

describe("ManagePanel", () => {
  beforeEach(() => useProjectStore.setState(useProjectStore.getInitialState(), true));

  it("draw -> capture stroke -> Add commits a region", () => {
    useProjectStore.getState().initFromPhoto(photo());
    render(<MantineProvider><ManagePanel /></MantineProvider>);
    fireEvent.click(screen.getByText(/Draw region/));
    fireEvent.click(screen.getByText("mock-draw"));   // draft gets one ring
    fireEvent.click(screen.getByText(/^Add/));
    expect(useProjectStore.getState().angles[0].book.drawn).toHaveLength(1);
  });

  it("delete removes the selected drawn region", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo());
    st.addRegion([[[0, 0], [1, 0], [1, 1]]], "helmet");  // selected = 1
    render(<MantineProvider><ManagePanel /></MantineProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Delete region" }));
    expect(useProjectStore.getState().angles[0].book.drawn).toHaveLength(0);
  });
});
