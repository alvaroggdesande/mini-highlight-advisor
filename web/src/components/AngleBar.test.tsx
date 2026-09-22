import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { useProjectStore } from "../store/projectStore";
import { AngleBar } from "./AngleBar";

const photo = (id: string) => ({ photo_id: id, width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#000" }], coverage: [1], material: "matte" } });

describe("AngleBar", () => {
  beforeEach(() => useProjectStore.setState(useProjectStore.getInitialState(), true));

  it("switches the active angle when a different angle is picked", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p0"));
    st.addAngle(photo("p1"));      // active -> 1
    render(<AngleBar />);
    fireEvent.click(screen.getByText("angle 1"));
    expect(useProjectStore.getState().activeAngle).toBe(0);
  });

  it("remove is disabled with a single angle", () => {
    useProjectStore.getState().initFromPhoto(photo("p0"));
    render(<AngleBar />);
    expect((screen.getByText(/Remove angle/) as HTMLButtonElement).disabled).toBe(true);
  });
});
