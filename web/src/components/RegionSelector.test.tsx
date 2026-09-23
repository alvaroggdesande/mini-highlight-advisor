import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { useProjectStore } from "../store/projectStore";
import { RegionSelector } from "./RegionSelector";

const photo = () => ({ photo_id: "p", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#000" }], coverage: [1], material: "matte" } });

describe("RegionSelector", () => {
  beforeEach(() => useProjectStore.setState(useProjectStore.getInitialState(), true));

  it("lists whole + drawn and switches selection on click", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo());
    st.addRegion([[[0, 0], [1, 0], [1, 1]]], "helmet");
    render(<MantineProvider><RegionSelector /></MantineProvider>);
    fireEvent.click(screen.getByText(/Whole mini/));
    expect(useProjectStore.getState().angles[0].book.selected).toBe(0);
    fireEvent.click(screen.getByText(/helmet/));
    expect(useProjectStore.getState().angles[0].book.selected).toBe(1);
  });
});
