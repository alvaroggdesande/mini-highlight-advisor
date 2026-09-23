import { describe, it, expect, beforeEach } from "vitest";
import { useProjectStore, activeBookOf } from "./projectStore";
import type { PhotoResponse } from "../api/types";

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);

describe("undo", () => {
  beforeEach(() => { reset(); useProjectStore.getState().initFromPhoto(photo()); });

  it("restores the palette captured by snapshotUndo", () => {
    const s = useProjectStore.getState();
    s.snapshotUndo();
    s.setHexSlot(0, 0, "#00ff00");
    expect(activeBookOf(useProjectStore.getState())!.whole.palette[0].hex).toBe("#00ff00");
    useProjectStore.getState().undo();
    expect(activeBookOf(useProjectStore.getState())!.whole.palette[0].hex).toBe("#111");
    expect(useProjectStore.getState().undoSnapshot).toBeNull();
  });

  it("undo is a no-op when there is no snapshot", () => {
    const s = useProjectStore.getState();
    s.setHexSlot(0, 0, "#00ff00");
    s.undo();
    expect(activeBookOf(useProjectStore.getState())!.whole.palette[0].hex).toBe("#00ff00");
  });
});
