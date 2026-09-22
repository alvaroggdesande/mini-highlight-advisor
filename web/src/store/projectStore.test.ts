import { describe, it, expect, beforeEach } from "vitest";
import { useProjectStore } from "./projectStore";

const reset = () => useProjectStore.setState(useProjectStore.getInitialState());

describe("projectStore", () => {
  beforeEach(reset);

  it("setPhoto seeds whole + dims from response", () => {
    useProjectStore.getState().setPhoto({
      photo_id: "p1", width: 30, height: 40, quality_checks: [],
      default_whole: { palette: [{ name: "a", hex: "#000000" }], coverage: [1.0], material: "matte" },
    });
    const s = useProjectStore.getState();
    expect(s.photoId).toBe("p1");
    expect(s.width).toBe(30);
    expect(s.whole?.coverage).toEqual([1.0]);
  });

  it("setBandCount resizes palette+coverage and coverage sums to ~1", () => {
    const st = useProjectStore.getState();
    st.setPhoto({ photo_id: "p", width: 1, height: 1, quality_checks: [],
      default_whole: { palette: [{ name: "a", hex: "#000000" }], coverage: [1.0], material: "matte" } });
    st.setBandCount(4);
    const w = useProjectStore.getState().whole!;
    expect(w.palette).toHaveLength(4);
    expect(w.coverage).toHaveLength(4);
    expect(Math.abs(w.coverage.reduce((a, b) => a + b, 0) - 1)).toBeLessThan(1e-6);
  });
});
