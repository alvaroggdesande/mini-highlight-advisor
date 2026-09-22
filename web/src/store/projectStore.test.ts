import { describe, it, expect, beforeEach } from "vitest";
import { useProjectStore, activeBookOf } from "./projectStore";
import type { PhotoResponse } from "../api/types";

const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);
const photo = (id: string, w = 100, h = 100): PhotoResponse => ({
  photo_id: id, width: w, height: h, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#202020" }, { name: "b", hex: "#e0e0e0" }],
                   coverage: [0.5, 0.5], material: "matte" },
});

describe("projectStore regions + angles", () => {
  beforeEach(reset);

  it("initFromPhoto creates angle 0 with a whole book", () => {
    useProjectStore.getState().initFromPhoto(photo("p1"));
    const s = useProjectStore.getState();
    expect(s.angles).toHaveLength(1);
    expect(s.activeAngle).toBe(0);
    expect(activeBookOf(s)!.whole.palette).toHaveLength(2);
    expect(activeBookOf(s)!.selected).toBe(0);
  });

  it("addRegion appends a drawn region, selects it, seeds neutral ramp", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion([[[10, 10], [20, 10], [20, 20]]], "helmet");
    const b = activeBookOf(useProjectStore.getState())!;
    expect(b.drawn).toHaveLength(1);
    expect(b.drawn[0].name).toBe("helmet");
    expect(b.selected).toBe(1);
    expect(b.drawn[0].palette.length).toBe(b.whole.palette.length);
  });

  it("setCoverage routes to the selected region", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion([[[0, 0], [1, 0], [1, 1]]]);       // selected = 1
    st.setCoverage([0.2, 0.8]);
    const b = activeBookOf(useProjectStore.getState())!;
    expect(b.drawn[0].coverage).toEqual([0.2, 0.8]);
    expect(b.whole.coverage).toEqual([0.5, 0.5]);   // whole untouched
  });

  it("removeRegion drops it and moves selection to whole", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion([[[0, 0], [1, 0], [1, 1]]]);
    st.removeRegion(1);
    const b = activeBookOf(useProjectStore.getState())!;
    expect(b.drawn).toHaveLength(0);
    expect(b.selected).toBe(0);
  });

  it("toggleBlank flips visibility on a drawn region", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion([[[0, 0], [1, 0], [1, 1]]]);
    st.toggleBlank(1);
    expect(activeBookOf(useProjectStore.getState())!.drawn[0].blank).toBe(true);
  });

  it("angles are isolated: editing angle 1 does not touch angle 0", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p0"));
    st.addRegion([[[0, 0], [1, 0], [1, 1]]], "onA0");
    st.addAngle(photo("p1"));                        // activeAngle -> 1
    expect(useProjectStore.getState().activeAngle).toBe(1);
    st.addRegion([[[2, 2], [3, 2], [3, 3]]], "onA1");
    const s = useProjectStore.getState();
    expect(s.angles[0].book.drawn.map((r) => r.name)).toEqual(["onA0"]);
    expect(s.angles[1].book.drawn.map((r) => r.name)).toEqual(["onA1"]);
  });

  it("setPreview stores preview on the active angle only", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p0"));
    st.addAngle(photo("p1"));
    st.setPreview("data:img", "tok");
    const s = useProjectStore.getState();
    expect(s.angles[1].preview).toBe("data:img");
    expect(s.angles[0].preview).toBeUndefined();
  });
});
