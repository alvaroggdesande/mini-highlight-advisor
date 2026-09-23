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

describe("projectStore colour extensions", () => {
  beforeEach(reset);

  it("setSurface updates whole when g=0", () => {
    useProjectStore.getState().initFromPhoto(photo("p1"));
    useProjectStore.getState().setSurface(0, "metal");
    expect(activeBookOf(useProjectStore.getState())!.whole.surface).toBe("metal");
  });

  it("setSurface updates drawn region when g=1", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion([[[0, 0], [1, 0], [1, 1]]], "helm");
    st.setSurface(1, "bone");
    expect(activeBookOf(useProjectStore.getState())!.drawn[0].surface).toBe("bone");
  });

  it("setTone updates whole when g=0", () => {
    useProjectStore.getState().initFromPhoto(photo("p1"));
    useProjectStore.getState().setTone(0, "warm");
    expect(activeBookOf(useProjectStore.getState())!.whole.tone).toBe("warm");
  });

  it("setMaterial updates whole material", () => {
    useProjectStore.getState().initFromPhoto(photo("p1"));
    useProjectStore.getState().setMaterial(0, "metallic");
    expect(activeBookOf(useProjectStore.getState())!.whole.material).toBe("metallic");
  });

  it("setHeroHex persists to book", () => {
    useProjectStore.getState().initFromPhoto(photo("p1"));
    useProjectStore.getState().setHeroHex("#c0392b");
    expect(activeBookOf(useProjectStore.getState())!.hero_hex).toBe("#c0392b");
  });

  it("setMood and setVariant persist", () => {
    useProjectStore.getState().initFromPhoto(photo("p1"));
    useProjectStore.getState().setMood("grimdark");
    useProjectStore.getState().setVariant("triadic");
    const b = activeBookOf(useProjectStore.getState())!;
    expect(b.mood).toBe("grimdark");
    expect(b.variant).toBe("triadic");
  });

  it("setRampState stores midtone and variant on drawn region", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion([[[0, 0], [1, 0], [1, 1]]]);
    st.setRampState(1, "#8b4513", "complementary");
    const r = activeBookOf(useProjectStore.getState())!.drawn[0];
    expect(r.ramp_midtone).toBe("#8b4513");
    expect(r.ramp_variant).toBe("complementary");
  });

  it("setPaletteAt replaces whole palette when g=0", () => {
    useProjectStore.getState().initFromPhoto(photo("p1"));
    const pal = [{ name: "x", hex: "#ff0000", code: "X1", finish: "matte" }];
    useProjectStore.getState().setPaletteAt(0, pal);
    expect(activeBookOf(useProjectStore.getState())!.whole.palette).toEqual(pal);
  });

  it("setPaletteSlot replaces one slot", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    const paint = { name: "Red", hex: "#ff0000", code: "R1", finish: "matte" };
    st.setPaletteSlot(0, 0, paint);
    expect(activeBookOf(useProjectStore.getState())!.whole.palette[0]).toEqual(paint);
  });

  it("setHexSlot creates custom entry with empty code", () => {
    useProjectStore.getState().initFromPhoto(photo("p1"));
    useProjectStore.getState().setHexSlot(0, 1, "#00ff00");
    const slot = activeBookOf(useProjectStore.getState())!.whole.palette[1];
    expect(slot.code).toBe("");
    expect(slot.hex).toBe("#00ff00");
    expect(slot.name).toBe("custom");
  });

  it("saveScheme snapshots current palettes keyed by region id", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion([[[0, 0], [1, 0], [1, 1]]], "helm");
    st.saveScheme("my scheme");
    const b = activeBookOf(useProjectStore.getState())!;
    expect(b.schemes).toHaveLength(1);
    expect(b.schemes[0].name).toBe("my scheme");
    expect("__whole__" in b.schemes[0].palettes).toBe(true);
    expect(b.drawn[0].id in b.schemes[0].palettes).toBe(true);
  });

  it("applyScheme restores palettes; silently skips missing region ids", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion([[[0, 0], [1, 0], [1, 1]]], "helm");
    st.setHexSlot(0, 0, "#ff0000");
    st.saveScheme("snap");
    st.setHexSlot(0, 0, "#0000ff");   // mutate after snapshot
    const schemeId = activeBookOf(useProjectStore.getState())!.schemes[0].id;
    st.applyScheme(schemeId);
    expect(activeBookOf(useProjectStore.getState())!.whole.palette[0].hex).toBe("#ff0000");
  });

  it("applyScheme silently skips region ids not in current book", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    // Inject a scheme with a stale region id
    const staleScheme: import("./projectStore").Scheme = {
      id: "sch1", name: "old",
      palettes: { "__whole__": [{ name: "a", hex: "#aaaaaa" }], "stale-id": [] },
    };
    st.initFromPhoto(photo("p1"));
    const b = activeBookOf(useProjectStore.getState())!;
    useProjectStore.setState({
      angles: [{ ...useProjectStore.getState().angles[0], book: { ...b, schemes: [staleScheme] } }]
    });
    expect(() => st.applyScheme("sch1")).not.toThrow();
  });

  it("deleteScheme removes scheme by id", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.saveScheme("A");
    st.saveScheme("B");
    const b = activeBookOf(useProjectStore.getState())!;
    st.deleteScheme(b.schemes[0].id);
    expect(activeBookOf(useProjectStore.getState())!.schemes).toHaveLength(1);
    expect(activeBookOf(useProjectStore.getState())!.schemes[0].name).toBe("B");
  });
});

describe("projectStore project persistence", () => {
  beforeEach(reset);

  it("initFromProject hydrates angles and sets project meta", () => {
    const manifest: import("../api/types").ProjectManifestDto = {
      name: "Iron Warrior",
      slug: "iron-warrior",
      active_angle: 0,
      updated_at: "2026-01-01T00:00:00Z",
      angles: [
        {
          id: "a1",
          label: "front",
          photo_id: "ph001",
          width: 640,
          height: 480,
          book: {
            whole: { palette: [{ name: "base", hex: "#333" }], coverage: [1], material: "matte" },
            drawn: [],
            selected: 0,
            schemes: [],
          },
          settings: {
            edge_hl: true, edge_extreme: false, edge_sens: 0.5,
            relief_cap: true, per_region_norm: false,
          },
        },
      ],
    };
    useProjectStore.getState().initFromProject(manifest);
    const s = useProjectStore.getState();
    expect(s.projectName).toBe("Iron Warrior");
    expect(s.slug).toBe("iron-warrior");
    expect(s.activeAngle).toBe(0);
    expect(s.angles).toHaveLength(1);
    expect(s.angles[0].id).toBe("a1");
    expect(s.angles[0].photoId).toBe("ph001");
    expect(s.angles[0].width).toBe(640);
    expect(s.angles[0].height).toBe(480);
    expect(s.angles[0].qualityChecks).toEqual([]);
    expect(s.angles[0].preview).toBeUndefined();
    expect(s.angles[0].resultToken).toBeUndefined();
  });

  it("initFromPhoto clears projectName and slug", () => {
    useProjectStore.getState().setProjectMeta("old name", "old-slug");
    useProjectStore.getState().initFromPhoto({
      photo_id: "p2", width: 100, height: 100, quality_checks: [],
      default_whole: { palette: [], coverage: [], material: "matte" },
    });
    const s = useProjectStore.getState();
    expect(s.projectName).toBeNull();
    expect(s.slug).toBeNull();
  });

  it("setProjectMeta stores name and slug", () => {
    useProjectStore.getState().setProjectMeta("My Mini", "my-mini");
    expect(useProjectStore.getState().projectName).toBe("My Mini");
    expect(useProjectStore.getState().slug).toBe("my-mini");
  });

  it("initFromProject preserves drawn region blank flag default", () => {
    const manifest: import("../api/types").ProjectManifestDto = {
      name: "Test", slug: "test", active_angle: 0, updated_at: "",
      angles: [{
        id: "a1", label: "angle 1", photo_id: "ph1",
        book: {
          whole: { palette: [], coverage: [], material: "matte" },
          drawn: [{ id: "r1", name: "helm", rings: [], palette: [], coverage: [], material: "matte" }],
          selected: 0, schemes: [],
        },
        settings: { edge_hl: true, edge_extreme: false, edge_sens: 0.5, relief_cap: true, per_region_norm: false },
      }],
    };
    useProjectStore.getState().initFromProject(manifest);
    const drawn = useProjectStore.getState().angles[0].book.drawn;
    expect(drawn[0].blank).toBe(false);
  });
});
