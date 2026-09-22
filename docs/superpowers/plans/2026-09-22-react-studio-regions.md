# Studio Regions Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add lasso regions (react-konva) and multi-angle support to the React studio, wired into the live-preview `/api/analyze` loop.

**Architecture:** The backend gains region rasterization (points → `polygons_to_mask` → `Region`) with a `mask_cache`, plus a photo-image endpoint that serves the canvas background. The frontend Zustand store is reshaped from flat/single-angle to the manifest shape (`angles[] → book:{whole, drawn[]}`); region outlines and selection are drawn as client-side konva vectors from image-space point rings that persist and travel over HTTP.

**Tech Stack:** FastAPI + pydantic + numpy/PIL/opencv (backend); Vite + React 19 + TypeScript + Zustand + react-konva + Vitest (frontend).

**Spec:** `docs/superpowers/specs/2026-09-22-react-studio-regions-design.md`

## Global Constraints

- **Branch:** `feat/react-studio-regions` — feature branch + PR, never commit to `main` (repo rule).
- **Core is untouched:** `src/mini_highlight_advisor/` is read-only for this slice; the backend is a thin adapter that calls existing functions (`analyze_regions`, `polygons_to_mask`, `prepare_shading`).
- **No `projects.py` changes:** save/load serialization (the v5→v6 `points` bump) is a later slice; `rings` lives only in the in-memory store here.
- **Coordinate invariant:** region points **persist and travel in image space**. Display↔image scaling uses `dispW = min(600, srcW)`, `dispH = round(srcH * dispW / srcW)` and `sx = srcW/dispW, sy = srcH/dispH`, exactly matching `mini_highlight_advisor.regions.scale_points`.
- **Region geometry is `rings`** (`number[][][]` / `list[list[tuple[float,float]]]`): a list of polygon rings unioned via `polygons_to_mask`. A single lasso is one ring.
- **Material is `"matte"`** for all regions this slice (Technique/ColourPanel are later slices).
- **Blank regions are not sent** to `/api/analyze` (filtered client-side), matching `RegionBook.analyze_args`.
- **Frontend tests:** Vitest (`npm test` in `web/`). Backend tests: `.venv/Scripts/python -m pytest backend/tests/ -v`.
- **konva in jsdom:** the HTML canvas is unavailable in jsdom, so konva rendering is **not** unit-tested; geometry logic is tested as pure functions and `RegionCanvas` tests mock `react-konva`.

---

### Task 1: Backend — regions in `/api/analyze` + `mask_cache`

**Files:**
- Modify: `backend/schemas.py` (add `RegionModel`, extend `AnalyzeRequest`)
- Modify: `backend/main.py:45-66` (build regions + mask_cache in `analyze`)
- Test: `backend/tests/test_analyze.py`

**Interfaces:**
- Consumes: `mini_highlight_advisor.regions.polygons_to_mask(point_lists, shape) -> np.ndarray`, `mini_highlight_advisor.regions.Region(name, mask, palette, coverage, material=...)`, `mini_highlight_advisor.pipeline.analyze_regions(rgb, alpha, default_palette, coverage, regions, ..., whole_material, shading)`, existing `paint_from_model`, `shading_cache`.
- Produces: `AnalyzeRequest.regions: list[RegionModel]` where `RegionModel = {name: str, rings: list[list[tuple[float,float]]], palette: list[PaintColorModel], coverage: list[float], material: str}`; `mask_cache` LRU in `backend/main.py`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_analyze.py` (uploads a real bundled sample so `shading.mask` is non-empty):

```python
from fastapi.testclient import TestClient
from mini_highlight_advisor import samples
from backend.main import app, mask_cache

client = TestClient(app)


def _upload_sample() -> tuple[str, int, int]:
    photo = samples.list_photos()[0]
    with open(photo.path, "rb") as fh:
        r = client.post("/api/photo", files={"file": (photo.path.name, fh.read(), "image/png")})
    assert r.status_code == 200
    j = r.json()
    return j["photo_id"], j["width"], j["height"]


def _whole():
    return {"palette": [{"name": "a", "hex": "#202020"}, {"name": "b", "hex": "#e0e0e0"}],
            "coverage": [0.5, 0.5], "material": "matte"}


def test_analyze_with_region_returns_preview_and_token():
    pid, w, h = _upload_sample()
    ring = [[w * 0.3, h * 0.3], [w * 0.7, h * 0.3], [w * 0.7, h * 0.7], [w * 0.3, h * 0.7]]
    req = {"photo_id": pid, "whole": _whole(),
           "regions": [{"name": "helmet", "rings": [ring],
                        "palette": _whole()["palette"], "coverage": [0.5, 0.5], "material": "matte"}],
           "settings": {}}
    r = client.post("/api/analyze", json=req)
    assert r.status_code == 200
    body = r.json()
    assert body["preview_png"].startswith("data:image/png;base64,")
    assert len(body["result_token"]) == 16


def test_analyze_mask_cache_hits_on_identical_rings():
    pid, w, h = _upload_sample()
    ring = [[w * 0.3, h * 0.3], [w * 0.7, h * 0.3], [w * 0.7, h * 0.7], [w * 0.3, h * 0.7]]
    region = {"name": "r", "rings": [ring], "palette": _whole()["palette"],
              "coverage": [0.5, 0.5], "material": "matte"}
    req = {"photo_id": pid, "whole": _whole(), "regions": [region], "settings": {}}
    mask_cache._d.clear()
    client.post("/api/analyze", json=req)
    n_after_first = len(mask_cache._d)
    client.post("/api/analyze", json=req)  # identical rings -> no new cache entry
    assert len(mask_cache._d) == n_after_first == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_analyze.py -v`
Expected: FAIL — `AnalyzeRequest` rejects `regions` (422) and `mask_cache` does not exist (ImportError).

- [ ] **Step 3: Extend the schemas**

In `backend/schemas.py`, add below `PaintColorModel`:

```python
class RegionModel(BaseModel):
    name: str
    rings: list[list[tuple[float, float]]]
    palette: list[PaintColorModel]
    coverage: list[float]
    material: str = "matte"
```

And add to `AnalyzeRequest`:

```python
    regions: list[RegionModel] = Field(default_factory=list)
```

- [ ] **Step 4: Build regions + mask_cache in the endpoint**

In `backend/main.py`, add imports near the top:

```python
import json
from mini_highlight_advisor.regions import Region, polygons_to_mask
```

Add a cache next to the existing ones:

```python
mask_cache = LRU(maxsize=64)
```

Replace the body of `analyze` (currently passing `[]`) so it builds regions:

```python
@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    cached = shading_cache.get(req.photo_id)
    if cached is None:
        raise HTTPException(status_code=404, detail="unknown photo_id; re-upload the photo")
    rgb, alpha, shading = cached
    h, w = rgb.shape[:2]
    palette = [paint_from_model(p) for p in req.whole.palette]

    regions = []
    for rm in req.regions:
        rings = [[(float(x), float(y)) for x, y in ring] for ring in rm.rings]
        key = (req.photo_id, hashlib.sha256(json.dumps(rings).encode()).hexdigest())
        mask = mask_cache.get(key)
        if mask is None:
            mask = polygons_to_mask(rings, (h, w)) & shading.mask
            mask_cache.set(key, mask)
        regions.append(Region(
            name=rm.name, mask=mask,
            palette=[paint_from_model(p) for p in rm.palette],
            coverage=list(rm.coverage), material=rm.material,
        ))

    result = analyze_regions(
        rgb, alpha, palette, list(req.whole.coverage), regions,
        edges=req.settings.edge_hl, extreme_edge=req.settings.edge_extreme,
        edge_sensitivity=req.settings.edge_sens, relief_cap=req.settings.relief_cap,
        per_region_norm=req.settings.per_region_norm,
        whole_material=req.whole.material, shading=shading,
    )
    token = hashlib.sha256((req.photo_id + req.model_dump_json()).encode("utf-8")).hexdigest()[:16]
    result_cache.set(token, result)
    return {"preview_png": png_data_uri(result.combined_rgb), "result_token": token}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest backend/tests/test_analyze.py -v`
Expected: PASS (both new tests, plus the pre-existing whole-only analyze test still green).

- [ ] **Step 6: Commit**

```bash
git add backend/schemas.py backend/main.py backend/tests/test_analyze.py
git commit -m "feat(backend): regions in /api/analyze with mask_cache"
```

---

### Task 2: Backend — `GET /api/photo/{photo_id}/image`

**Files:**
- Modify: `backend/main.py` (new route)
- Test: `backend/tests/test_photo.py`

**Interfaces:**
- Consumes: `shading_cache` (holds `(rgb, alpha, shading)`), `backend.serialize.to_png_bytes(arr) -> bytes`.
- Produces: `GET /api/photo/{photo_id}/image` → `200 image/png` (cached rgb) or `404`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_photo.py`:

```python
from mini_highlight_advisor import samples


def test_photo_image_returns_png_for_known_id(client):
    photo = samples.list_photos()[0]
    with open(photo.path, "rb") as fh:
        pid = client.post("/api/photo", files={"file": (photo.path.name, fh.read(), "image/png")}).json()["photo_id"]
    r = client.get(f"/api/photo/{pid}/image")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_photo_image_404_for_unknown_id(client):
    r = client.get("/api/photo/deadbeef/image")
    assert r.status_code == 404
```

> If `test_photo.py` has no `client` fixture, add one: `@pytest.fixture\ndef client(): from backend.main import app; from fastapi.testclient import TestClient; return TestClient(app)` (or reuse the module's existing client pattern).

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_photo.py -v`
Expected: FAIL — route returns 404 for the known id too (route not defined).

- [ ] **Step 3: Add the route**

In `backend/main.py`, add import and route (place the route **above** the `StaticFiles` mount so `/api/*` wins):

```python
from fastapi.responses import Response
from backend.serialize import to_png_bytes
```

```python
@app.get("/api/photo/{photo_id}/image")
def photo_image(photo_id: str):
    cached = shading_cache.get(photo_id)
    if cached is None:
        raise HTTPException(status_code=404, detail="unknown photo_id; re-upload the photo")
    rgb, _alpha, _shading = cached
    return Response(content=to_png_bytes(rgb), media_type="image/png")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest backend/tests/test_photo.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_photo.py
git commit -m "feat(backend): GET /api/photo/{id}/image for canvas background"
```

---

### Task 3: Frontend — geometry + decimation pure utilities

**Files:**
- Create: `web/src/lib/geometry.ts`
- Create: `web/src/lib/geometry.test.ts`
- Create: `web/src/lib/id.ts`

**Interfaces:**
- Produces:
  - `type Pt = [number, number]`
  - `displaySize(srcW: number, srcH: number): { dispW: number; dispH: number }`
  - `toImageSpace(pt: Pt, srcW: number, srcH: number, dispW: number, dispH: number): Pt`
  - `toDisplaySpace(pt: Pt, srcW: number, srcH: number, dispW: number, dispH: number): Pt`
  - `decimate(points: Pt[], epsilon: number): Pt[]` (Douglas–Peucker)
  - `REGION_COLORS: string[]`, `REGION_EMOJIS: string[]`, `WHOLE_MINI_EMOJI: string`
  - `regionLabel(g: number, name: string): string`
  - `newId(): string` (in `id.ts`)

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/geometry.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { displaySize, toImageSpace, toDisplaySpace, decimate, regionLabel, REGION_EMOJIS } from "./geometry";

describe("geometry", () => {
  it("displaySize caps width at 600 and preserves aspect", () => {
    expect(displaySize(1200, 900)).toEqual({ dispW: 600, dispH: 450 });
    expect(displaySize(400, 800)).toEqual({ dispW: 400, dispH: 800 });
  });

  it("toImageSpace scales display point to source pixels (matches scale_points)", () => {
    const { dispW, dispH } = displaySize(1200, 900); // 600x450, sx=sy=2
    expect(toImageSpace([100, 50], 1200, 900, dispW, dispH)).toEqual([200, 100]);
  });

  it("toImageSpace -> toDisplaySpace round-trips", () => {
    const { dispW, dispH } = displaySize(1200, 900);
    const img = toImageSpace([123, 77], 1200, 900, dispW, dispH);
    const back = toDisplaySpace(img, 1200, 900, dispW, dispH);
    expect(back[0]).toBeCloseTo(123);
    expect(back[1]).toBeCloseTo(77);
  });

  it("decimate drops collinear points but keeps endpoints and corners", () => {
    const line: [number, number][] = [[0, 0], [1, 0], [2, 0], [3, 0], [3, 3]];
    const out = decimate(line, 0.5);
    expect(out).toContainEqual([0, 0]);
    expect(out).toContainEqual([3, 0]);
    expect(out).toContainEqual([3, 3]);
    expect(out.length).toBeLessThan(line.length);
  });

  it("regionLabel prefixes the region emoji cycling by index", () => {
    expect(regionLabel(1, "helmet")).toBe(`${REGION_EMOJIS[0]} helmet`);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (in `web/`): `npm test -- geometry`
Expected: FAIL — module `./geometry` not found.

- [ ] **Step 3: Implement the utilities**

Create `web/src/lib/geometry.ts`:

```ts
export type Pt = [number, number];

// Values mirror ui/geometry.py REGION_COLORS / REGION_EMOJIS (order = book index 1..N).
export const REGION_COLORS: string[] = ["#b432ff", "#3264ff", "#fad21e", "#32c832", "#ff3c3c"];
export const REGION_EMOJIS: string[] = ["🟣", "🔵", "🟡", "🟢", "🔴"];
export const WHOLE_MINI_EMOJI = "⬜";

export function displaySize(srcW: number, srcH: number): { dispW: number; dispH: number } {
  const dispW = Math.min(600, srcW);
  const dispH = Math.round((srcH * dispW) / srcW);
  return { dispW, dispH };
}

export function toImageSpace(pt: Pt, srcW: number, srcH: number, dispW: number, dispH: number): Pt {
  return [pt[0] * (srcW / dispW), pt[1] * (srcH / dispH)];
}

export function toDisplaySpace(pt: Pt, srcW: number, srcH: number, dispW: number, dispH: number): Pt {
  return [pt[0] * (dispW / srcW), pt[1] * (dispH / srcH)];
}

function perpDist(p: Pt, a: Pt, b: Pt): number {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const len = Math.hypot(dx, dy) || 1e-9;
  return Math.abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / len;
}

export function decimate(points: Pt[], epsilon: number): Pt[] {
  if (points.length < 3) return points.slice();
  let maxD = 0, idx = 0;
  const a = points[0], b = points[points.length - 1];
  for (let i = 1; i < points.length - 1; i++) {
    const d = perpDist(points[i], a, b);
    if (d > maxD) { maxD = d; idx = i; }
  }
  if (maxD <= epsilon) return [a, b];
  const left = decimate(points.slice(0, idx + 1), epsilon);
  const right = decimate(points.slice(idx), epsilon);
  return left.slice(0, -1).concat(right);
}

export function regionLabel(g: number, name: string): string {
  if (g === 0) return `${WHOLE_MINI_EMOJI} ${name}`;
  return `${REGION_EMOJIS[(g - 1) % REGION_EMOJIS.length]} ${name}`;
}
```

Create `web/src/lib/id.ts`:

```ts
export const newId = (): string =>
  globalThis.crypto?.randomUUID?.() ?? `id-${Math.random().toString(36).slice(2)}`;
```

- [ ] **Step 4: Run tests to verify they pass**

Run (in `web/`): `npm test -- geometry`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/geometry.ts web/src/lib/geometry.test.ts web/src/lib/id.ts
git commit -m "feat(web): image<->display scaling, decimation, region constants"
```

---

### Task 4: Frontend — store reshape to `angles[] / book`, API types, rewire consumers

**Files:**
- Modify: `web/src/api/types.ts` (add `RegionPayload`, `QualityCheck` reuse, extend `AnalyzeRequest`)
- Rewrite: `web/src/store/projectStore.ts`
- Rewrite: `web/src/store/projectStore.test.ts`
- Modify: `web/src/hooks/useAnalyze.ts`
- Modify: `web/src/components/PhotoUploader.tsx`
- Modify: `web/src/components/BandControl.tsx`
- Modify: `web/src/components/PreviewImage.tsx`
- Modify: `web/src/App.tsx` (guarded rendering — full layout in Task 8)

**Interfaces:**
- Consumes: `newId` (Task 3), `PhotoResponse`, `Whole`, `Settings`, `PaintColor`, `QualityCheck`.
- Produces (store):
  - Types: `DrawnRegion = { id: string; name: string; rings: number[][][]; palette: PaintColor[]; coverage: number[]; material: string; blank: boolean }`; `Book = { whole: Whole; drawn: DrawnRegion[]; selected: number }`; `Angle = { id: string; label: string; photoId?: string; width?: number; height?: number; qualityChecks: QualityCheck[]; book: Book; settings: Settings; preview?: string; resultToken?: string; error?: string }`.
  - State: `{ activeAngle: number; angles: Angle[] }`.
  - Selectors (exported pure fns): `activeAngleOf(s): Angle | undefined`, `activeBookOf(s): Book | undefined`.
  - Actions: `initFromPhoto(res)`, `addAngle(res)`, `switchAngle(i)`, `renameAngle(i, label)`, `removeAngle(i)`, `setSelected(g)`, `addRegion(rings, name?)`, `removeRegion(g)`, `renameRegion(g, name)`, `toggleBlank(g)`, `setCoverage(cov)`, `setBandCount(n)`, `setPreview(png, token)`, `setError(msg?)`.
  - `setCoverage`/`setBandCount` operate on `book.selected` (0 = whole, 1..N = drawn).
- Produces (types.ts): `RegionPayload = { name: string; rings: number[][][]; palette: PaintColor[]; coverage: number[]; material: string }`; `AnalyzeRequest` gains `regions: RegionPayload[]`.

- [ ] **Step 1: Write the failing test**

Rewrite `web/src/store/projectStore.test.ts`:

```ts
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (in `web/`): `npm test -- projectStore`
Expected: FAIL — `initFromPhoto` / `activeBookOf` not exported.

- [ ] **Step 3: Extend API types**

In `web/src/api/types.ts`, add and extend:

```ts
export interface RegionPayload {
  name: string; rings: number[][][];
  palette: PaintColor[]; coverage: number[]; material: string;
}
export interface AnalyzeRequest {
  photo_id: string; whole: Whole; regions: RegionPayload[]; settings?: Partial<Settings>;
}
```

(Delete the old `AnalyzeRequest` interface — `regions` is now required.)

- [ ] **Step 4: Rewrite the store**

Replace `web/src/store/projectStore.ts`:

```ts
import { create } from "zustand";
import type { PhotoResponse, Settings, Whole, PaintColor, QualityCheck } from "../api/types";
import { newId } from "../lib/id";

export const DEFAULT_SETTINGS: Settings = {
  edge_hl: true, edge_extreme: false, edge_sens: 0.5, relief_cap: true, per_region_norm: false,
};

export interface DrawnRegion {
  id: string; name: string; rings: number[][][];
  palette: PaintColor[]; coverage: number[]; material: string; blank: boolean;
}
export interface Book { whole: Whole; drawn: DrawnRegion[]; selected: number; }
export interface Angle {
  id: string; label: string;
  photoId?: string; width?: number; height?: number; qualityChecks: QualityCheck[];
  book: Book; settings: Settings;
  preview?: string; resultToken?: string; error?: string;
}

interface State {
  activeAngle: number;
  angles: Angle[];
  initFromPhoto(res: PhotoResponse): void;
  addAngle(res: PhotoResponse): void;
  switchAngle(i: number): void;
  renameAngle(i: number, label: string): void;
  removeAngle(i: number): void;
  setSelected(g: number): void;
  addRegion(rings: number[][][], name?: string): void;
  removeRegion(g: number): void;
  renameRegion(g: number, name: string): void;
  toggleBlank(g: number): void;
  setCoverage(cov: number[]): void;
  setBandCount(n: number): void;
  setPreview(png: string, token: string): void;
  setError(msg?: string): void;
}

export const activeAngleOf = (s: { angles: Angle[]; activeAngle: number }): Angle | undefined =>
  s.angles[s.activeAngle];
export const activeBookOf = (s: { angles: Angle[]; activeAngle: number }): Book | undefined =>
  activeAngleOf(s)?.book;

function makeAngle(res: PhotoResponse, label: string, settings: Settings): Angle {
  return {
    id: newId(), label, photoId: res.photo_id, width: res.width, height: res.height,
    qualityChecks: res.quality_checks,
    book: { whole: res.default_whole, drawn: [], selected: 0 },
    settings,
  };
}

function resize<T>(arr: T[], n: number, fill: (i: number) => T): T[] {
  const out = arr.slice(0, n);
  for (let i = out.length; i < n; i++) out.push(fill(i));
  return out;
}

// Immutably update the active angle's book.
function patchBook(s: State, fn: (b: Book) => Book): Partial<State> {
  const angle = s.angles[s.activeAngle];
  if (!angle) return {};
  const angles = s.angles.slice();
  angles[s.activeAngle] = { ...angle, book: fn(angle.book) };
  return { angles };
}
function patchAngle(s: State, i: number, fn: (a: Angle) => Angle): Partial<State> {
  const angle = s.angles[i];
  if (!angle) return {};
  const angles = s.angles.slice();
  angles[i] = fn(angle);
  return { angles };
}

function neutralRegion(book: Book): DrawnRegion {
  const n = book.whole.palette.length;
  return {
    id: newId(), name: "", rings: [],
    palette: Array.from({ length: n }, () => ({ name: "band", hex: "#808080" })),
    coverage: Array.from({ length: n }, () => 1 / n),
    material: "matte", blank: false,
  };
}

export const useProjectStore = create<State>((set) => ({
  activeAngle: 0,
  angles: [],

  initFromPhoto: (res) => set({ activeAngle: 0, angles: [makeAngle(res, "angle 1", DEFAULT_SETTINGS)] }),

  addAngle: (res) => set((s) => {
    const settings = s.angles[s.activeAngle]?.settings ?? DEFAULT_SETTINGS;
    const angles = s.angles.concat(makeAngle(res, `angle ${s.angles.length + 1}`, settings));
    return { angles, activeAngle: angles.length - 1 };
  }),

  switchAngle: (i) => set((s) => (i >= 0 && i < s.angles.length ? { activeAngle: i } : {})),

  renameAngle: (i, label) => set((s) => {
    const clean = label.trim();
    return clean ? patchAngle(s, i, (a) => ({ ...a, label: clean })) : {};
  }),

  removeAngle: (i) => set((s) => {
    if (s.angles.length <= 1) return {};
    const angles = s.angles.slice();
    angles.splice(i, 1);
    const activeAngle = s.activeAngle > i ? s.activeAngle - 1
      : s.activeAngle === i ? Math.max(0, i - 1) : s.activeAngle;
    return { angles, activeAngle };
  }),

  setSelected: (g) => set((s) => patchBook(s, (b) =>
    g >= 0 && g <= b.drawn.length ? { ...b, selected: g } : b)),

  addRegion: (rings, name) => set((s) => patchBook(s, (b) => {
    const region = { ...neutralRegion(b), rings, name: (name ?? `region ${b.drawn.length + 1}`).trim() };
    const drawn = b.drawn.concat(region);
    return { ...b, drawn, selected: drawn.length };
  })),

  removeRegion: (g) => set((s) => patchBook(s, (b) => {
    if (g < 1 || g > b.drawn.length) return b;
    const drawn = b.drawn.slice();
    drawn.splice(g - 1, 1);
    const selected = b.selected === g ? g - 1 : b.selected > g ? b.selected - 1 : b.selected;
    return { ...b, drawn, selected };
  })),

  renameRegion: (g, name) => set((s) => patchBook(s, (b) => {
    const clean = name.trim();
    if (g < 1 || g > b.drawn.length || !clean) return b;
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], name: clean };
    return { ...b, drawn };
  })),

  toggleBlank: (g) => set((s) => patchBook(s, (b) => {
    if (g < 1 || g > b.drawn.length) return b;
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], blank: !drawn[g - 1].blank };
    return { ...b, drawn };
  })),

  setCoverage: (cov) => set((s) => patchBook(s, (b) => {
    if (b.selected === 0) return { ...b, whole: { ...b.whole, coverage: cov } };
    const drawn = b.drawn.slice();
    drawn[b.selected - 1] = { ...drawn[b.selected - 1], coverage: cov };
    return { ...b, drawn };
  })),

  setBandCount: (n) => set((s) => patchBook(s, (b) => {
    const cur = b.selected === 0 ? b.whole : b.drawn[b.selected - 1];
    const palette = resize(cur.palette, n, () => ({ name: "band", hex: "#808080" }));
    const raw = resize(cur.coverage, n, () => 1 / n);
    const sum = raw.reduce((a, c) => a + c, 0);
    const coverage = sum > 0 ? raw.map((v) => v / sum) : raw.map(() => 1 / n);
    if (b.selected === 0) return { ...b, whole: { ...b.whole, palette, coverage } };
    const drawn = b.drawn.slice();
    drawn[b.selected - 1] = { ...drawn[b.selected - 1], palette, coverage };
    return { ...b, drawn };
  })),

  setPreview: (png, token) => set((s) =>
    patchAngle(s, s.activeAngle, (a) => ({ ...a, preview: png, resultToken: token, error: undefined }))),

  setError: (msg) => set((s) => patchAngle(s, s.activeAngle, (a) => ({ ...a, error: msg }))),
}));
```

- [ ] **Step 5: Run store tests to verify they pass**

Run (in `web/`): `npm test -- projectStore`
Expected: PASS.

- [ ] **Step 6: Rewire the four consumers**

`web/src/hooks/useAnalyze.ts` — read the active angle, send non-blank regions:

```ts
import { useEffect, useRef } from "react";
import { analyze } from "../api/client";
import { useProjectStore, activeAngleOf } from "../store/projectStore";
import type { RegionPayload } from "../api/types";

export function useAnalyze(delay = 150) {
  const angle = useProjectStore(activeAngleOf);
  const setPreview = useProjectStore((s) => s.setPreview);
  const setError = useProjectStore((s) => s.setError);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const photoId = angle?.photoId;
  const book = angle?.book;
  const settings = angle?.settings;

  useEffect(() => {
    if (!photoId || !book || !settings) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const regions: RegionPayload[] = book.drawn
          .filter((r) => !r.blank && r.rings.length > 0)
          .map((r) => ({ name: r.name, rings: r.rings, palette: r.palette,
                         coverage: r.coverage, material: r.material }));
        const res = await analyze({ photo_id: photoId, whole: book.whole, regions, settings });
        setPreview(res.preview_png, res.result_token);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    }, delay);
    return () => clearTimeout(timer.current);
  }, [photoId, book, settings, delay, setPreview, setError]);
}
```

`web/src/components/PhotoUploader.tsx` — first upload calls `initFromPhoto` (change the two `setPhoto` usages):

```ts
  const initFromPhoto = useProjectStore((s) => s.initFromPhoto);
  // ...
  async function handleBlob(blob: Blob, name: string) {
    try { initFromPhoto(await uploadPhoto(blob, name)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }
```

> `setError` with no active angle is a no-op (guarded by `patchAngle`); that's fine — an upload failure before any angle exists simply shows nothing, matching prior behavior where the preview stayed empty.

`web/src/components/BandControl.tsx` — read the selected region's palette length:

```ts
import { useProjectStore, activeBookOf } from "../store/projectStore";

export function BandControl() {
  const book = useProjectStore(activeBookOf);
  const setBandCount = useProjectStore((s) => s.setBandCount);
  if (!book) return null;
  const cur = book.selected === 0 ? book.whole : book.drawn[book.selected - 1];
  return (
    <label>
      Bands: {cur.palette.length}
      <input type="range" min={1} max={8} value={cur.palette.length}
        onChange={(e) => setBandCount(Number(e.target.value))} />
    </label>
  );
}
```

`web/src/components/PreviewImage.tsx` — read from the active angle:

```ts
import { useProjectStore, activeAngleOf } from "../store/projectStore";

export function PreviewImage() {
  const angle = useProjectStore(activeAngleOf);
  if (angle?.error) return <p role="alert" style={{ color: "crimson" }}>Analyze failed: {angle.error}</p>;
  if (!angle?.preview) return <p>Upload a photo or pick a sample to see the preview.</p>;
  return <img src={angle.preview} alt="painted preview" style={{ maxWidth: "100%" }} />;
}
```

`web/src/App.tsx` — guard on angles (full layout comes in Task 8):

```tsx
import { PhotoUploader } from "./components/PhotoUploader";
import { PreviewImage } from "./components/PreviewImage";
import { BandControl } from "./components/BandControl";
import { useAnalyze } from "./hooks/useAnalyze";
import { useProjectStore } from "./store/projectStore";

export default function App() {
  useAnalyze();
  const hasAngle = useProjectStore((s) => s.angles.length > 0);
  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: 16 }}>
      <h1>Mini Highlight Advisor</h1>
      {!hasAngle ? <PhotoUploader /> : (<><BandControl /><PreviewImage /></>)}
    </main>
  );
}
```

- [ ] **Step 7: Update the PhotoUploader test and run the full suite**

`web/src/components/PhotoUploader.test.tsx` currently asserts `setPhoto`; update any reference to the store to assert `initFromPhoto` populated `angles` (e.g. after a successful upload, `useProjectStore.getState().angles).toHaveLength(1)`). Then:

Run (in `web/`): `npm test` and `npm run build`
Expected: PASS; `tsc -b` clean (no references to removed `whole`/`photoId`/`setPhoto`).

- [ ] **Step 8: Commit**

```bash
git add web/src/api/types.ts web/src/store/ web/src/hooks/useAnalyze.ts web/src/components/ web/src/App.tsx
git commit -m "feat(web): reshape store to angles[]/book; regions in analyze request"
```

---

### Task 5: Frontend — `RegionCanvas` (react-konva)

**Files:**
- Modify: `web/package.json` (add `konva`, `react-konva`)
- Create: `web/src/components/RegionCanvas.tsx`
- Create: `web/src/components/RegionCanvas.test.tsx`

**Interfaces:**
- Consumes: `displaySize`, `toImageSpace`, `toDisplaySpace`, `decimate`, `REGION_COLORS`, `Pt` (Task 3); store `activeAngleOf`, `activeBookOf`, `addRegion` (Task 4); backend `GET /api/photo/{id}/image` (Task 2).
- Produces: `<RegionCanvas drawing={boolean} draftRings={number[][][]} onDraftChange={(rings: number[][][]) => void} />` — a **controlled** component. It renders the active angle's photo (background) + existing region outlines + selection highlight from the store, and, when `drawing`, captures each freehand stroke and appends its decimated image-space ring by calling `onDraftChange(draftRings.concat([ring]))`. The parent (ManagePanel, Task 6) owns the draft-ring state and the Add/Cancel buttons; `RegionCanvas` holds no committed state of its own.

- [ ] **Step 1: Add konva dependencies**

Run (in `web/`): `npm install konva react-konva`
Expected: `package.json` dependencies gain `konva` and `react-konva` (react-konva ^19 for React 19). Commit the lockfile change with the component.

- [ ] **Step 2: Write the failing test (mock react-konva)**

Create `web/src/components/RegionCanvas.test.tsx`. jsdom lacks canvas, so mock `react-konva` with plain divs and assert the controlled draft contract + image URL:

```tsx
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
```

> Add `use-image` (`npm install use-image`) as the konva image-loading helper, or load the image via a plain `Image()` in a `useEffect`; the plan uses `use-image` for brevity.

- [ ] **Step 3: Run test to verify it fails**

Run (in `web/`): `npm test -- RegionCanvas`
Expected: FAIL — module `./RegionCanvas` not found.

- [ ] **Step 4: Implement `RegionCanvas`**

Create `web/src/components/RegionCanvas.tsx`:

```tsx
import { useRef } from "react";
import { Stage, Layer, Line, Image as KonvaImage } from "react-konva";
import useImage from "use-image";
import { useProjectStore, activeAngleOf, activeBookOf } from "../store/projectStore";
import { displaySize, toImageSpace, toDisplaySpace, decimate, REGION_COLORS, type Pt } from "../lib/geometry";

const DECIMATE_EPS = 1.5;

interface Props {
  drawing: boolean;
  draftRings: number[][][];
  onDraftChange: (rings: number[][][]) => void;
}

export function RegionCanvas({ drawing, draftRings, onDraftChange }: Props) {
  const angle = useProjectStore(activeAngleOf);
  const book = useProjectStore(activeBookOf);
  const stroke = useRef<Pt[]>([]);
  const [image] = useImage(angle?.photoId ? `/api/photo/${angle.photoId}/image` : "");

  if (!angle || !book || !angle.width || !angle.height) return null;
  const srcW = angle.width, srcH = angle.height;
  const { dispW, dispH } = displaySize(srcW, srcH);
  const toDisp = (p: number[]): number[] => toDisplaySpace(p as Pt, srcW, srcH, dispW, dispH);
  const flat = (ring: number[][]): number[] => ring.flatMap((p) => toDisp(p));

  function pointerPt(e: any): Pt | null {
    const pos = e.target.getStage().getPointerPosition();
    return pos ? [pos.x, pos.y] : null;
  }
  function onDown(e: any) {
    if (!drawing) return;
    const p = pointerPt(e); if (p) stroke.current = [p];
  }
  function onMove(e: any) {
    if (!drawing || stroke.current.length === 0) return;
    const p = pointerPt(e); if (p) stroke.current = stroke.current.concat([p]);
  }
  function onUp() {
    if (!drawing || stroke.current.length < 3) { stroke.current = []; return; }
    const ring = decimate(stroke.current, DECIMATE_EPS).map((p) => toImageSpace(p, srcW, srcH, dispW, dispH));
    onDraftChange(draftRings.concat([ring]));
    stroke.current = [];
  }

  return (
    <Stage width={dispW} height={dispH} onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp}
           onTouchStart={onDown} onTouchMove={onMove} onTouchEnd={onUp}>
      <Layer listening={false}>
        {image && <KonvaImage image={image} width={dispW} height={dispH} />}
      </Layer>
      <Layer>
        {book.drawn.map((r, i) =>
          r.rings.map((ring, j) => (
            <Line key={`${r.id}-${j}`} points={flat(ring)} closed
                  stroke={REGION_COLORS[i % REGION_COLORS.length]}
                  strokeWidth={i + 1 === book.selected ? 3 : 1.5}
                  opacity={r.blank ? 0.3 : 1} />
          )))}
        {draftRings.map((ring, j) => (
          <Line key={`draft-${j}`} points={flat(ring)} closed stroke="#ff28c8" strokeWidth={2}
                dash={[6, 4]} fill="rgba(255,40,200,0.15)" />
        ))}
      </Layer>
    </Stage>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run (in `web/`): `npm test -- RegionCanvas` then `npm run build`
Expected: PASS; build clean.

- [ ] **Step 6: Commit**

```bash
git add web/package.json web/package-lock.json web/src/components/RegionCanvas.tsx web/src/components/RegionCanvas.test.tsx
git commit -m "feat(web): RegionCanvas — konva bg + outline vectors + freehand capture"
```

---

### Task 6: Frontend — `RegionSelector` + `ManagePanel`

**Files:**
- Create: `web/src/components/RegionSelector.tsx`
- Create: `web/src/components/RegionSelector.test.tsx`
- Create: `web/src/components/ManagePanel.tsx`
- Create: `web/src/components/ManagePanel.test.tsx`

**Interfaces:**
- Consumes: store `activeBookOf`, `setSelected`, `toggleBlank`, `addRegion`, `removeRegion`, `renameRegion` (Task 4); `regionLabel` (Task 3); `RegionCanvas` (Task 5).
- Produces: `<RegionSelector />` (radio + blank toggles, self-contained on the store); `<ManagePanel />` (owns draw-mode + draft state, renders `RegionCanvas`, Add/Cancel, rename/delete for the selected region).

- [ ] **Step 1: Write the failing tests**

`web/src/components/RegionSelector.test.tsx`:

```tsx
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
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
    render(<RegionSelector />);
    fireEvent.click(screen.getByText(/Whole mini/));
    expect(useProjectStore.getState().angles[0].book.selected).toBe(0);
    fireEvent.click(screen.getByText(/helmet/));
    expect(useProjectStore.getState().angles[0].book.selected).toBe(1);
  });
});
```

`web/src/components/ManagePanel.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
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
    render(<ManagePanel />);
    fireEvent.click(screen.getByText(/Draw region/));
    fireEvent.click(screen.getByText("mock-draw"));   // draft gets one ring
    fireEvent.click(screen.getByText(/^Add/));
    expect(useProjectStore.getState().angles[0].book.drawn).toHaveLength(1);
  });

  it("delete removes the selected drawn region", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo());
    st.addRegion([[[0, 0], [1, 0], [1, 1]]], "helmet");  // selected = 1
    render(<ManagePanel />);
    fireEvent.click(screen.getByText(/Delete/));
    expect(useProjectStore.getState().angles[0].book.drawn).toHaveLength(0);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run (in `web/`): `npm test -- RegionSelector ManagePanel`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement `RegionSelector`**

Create `web/src/components/RegionSelector.tsx`:

```tsx
import { useProjectStore, activeBookOf } from "../store/projectStore";
import { regionLabel } from "../lib/geometry";

export function RegionSelector() {
  const book = useProjectStore(activeBookOf);
  const setSelected = useProjectStore((s) => s.setSelected);
  const toggleBlank = useProjectStore((s) => s.toggleBlank);
  if (!book) return null;
  const names = ["Whole mini", ...book.drawn.map((r) => r.name)];
  return (
    <fieldset>
      <legend>Region</legend>
      {names.map((name, g) => (
        <div key={g}>
          <label>
            <input type="radio" name="region" checked={book.selected === g}
                   onChange={() => setSelected(g)} />
            {regionLabel(g, name)}
          </label>
          {g >= 1 && (
            <label style={{ marginLeft: 8, fontSize: "0.85em" }}>
              <input type="checkbox" checked={!book.drawn[g - 1].blank}
                     onChange={() => toggleBlank(g)} /> visible
            </label>
          )}
        </div>
      ))}
    </fieldset>
  );
}
```

- [ ] **Step 4: Implement `ManagePanel`**

Create `web/src/components/ManagePanel.tsx`:

```tsx
import { useState } from "react";
import { useProjectStore, activeBookOf } from "../store/projectStore";
import { RegionCanvas } from "./RegionCanvas";

export function ManagePanel() {
  const book = useProjectStore(activeBookOf);
  const addRegion = useProjectStore((s) => s.addRegion);
  const removeRegion = useProjectStore((s) => s.removeRegion);
  const renameRegion = useProjectStore((s) => s.renameRegion);
  const [drawing, setDrawing] = useState(false);
  const [draftRings, setDraftRings] = useState<number[][][]>([]);
  const [name, setName] = useState("");

  if (!book) return null;
  const sel = book.selected;
  const defaultName = `region ${book.drawn.length + 1}`;

  function commit() {
    if (draftRings.length === 0) return;
    addRegion(draftRings, name.trim() || defaultName);
    setDrawing(false); setDraftRings([]); setName("");
  }
  function cancel() { setDrawing(false); setDraftRings([]); setName(""); }

  return (
    <div>
      <RegionCanvas drawing={drawing} draftRings={draftRings} onDraftChange={setDraftRings} />
      {!drawing ? (
        <button onClick={() => setDrawing(true)}>Draw region</button>
      ) : (
        <div>
          <input placeholder={defaultName} value={name} onChange={(e) => setName(e.target.value)} />
          <button onClick={commit}>Add region</button>
          <button onClick={cancel}>Cancel</button>
          {draftRings.length > 0 && <span> {draftRings.length} stroke(s)</span>}
        </div>
      )}
      {!drawing && sel >= 1 && (
        <div>
          <input value={book.drawn[sel - 1].name}
                 onChange={(e) => renameRegion(sel, e.target.value)} />
          <button onClick={() => removeRegion(sel)}>Delete region</button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run (in `web/`): `npm test -- RegionSelector ManagePanel` then `npm run build`
Expected: PASS; build clean.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/RegionSelector.tsx web/src/components/RegionSelector.test.tsx web/src/components/ManagePanel.tsx web/src/components/ManagePanel.test.tsx
git commit -m "feat(web): RegionSelector + ManagePanel (draw/add/rename/delete/blank)"
```

---

### Task 7: Frontend — `AngleBar`

**Files:**
- Create: `web/src/components/AngleBar.tsx`
- Create: `web/src/components/AngleBar.test.tsx`

**Interfaces:**
- Consumes: store `angles`, `activeAngle`, `addAngle`, `switchAngle`, `renameAngle`, `removeAngle` (Task 4); `uploadPhoto` (`web/src/api/client.ts`).
- Produces: `<AngleBar />` — switch/rename/remove the active angle + add a new angle from an uploaded photo.

- [ ] **Step 1: Write the failing test**

Create `web/src/components/AngleBar.test.tsx`:

```tsx
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (in `web/`): `npm test -- AngleBar`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `AngleBar`**

Create `web/src/components/AngleBar.tsx`:

```tsx
import { useProjectStore } from "../store/projectStore";
import { uploadPhoto } from "../api/client";

export function AngleBar() {
  const angles = useProjectStore((s) => s.angles);
  const active = useProjectStore((s) => s.activeAngle);
  const addAngle = useProjectStore((s) => s.addAngle);
  const switchAngle = useProjectStore((s) => s.switchAngle);
  const renameAngle = useProjectStore((s) => s.renameAngle);
  const removeAngle = useProjectStore((s) => s.removeAngle);
  const setError = useProjectStore((s) => s.setError);
  if (angles.length === 0) return null;

  async function onAdd(file: File) {
    try { addAngle(await uploadPhoto(file, file.name)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <div>
      <strong>Angles</strong>
      <div style={{ display: "flex", gap: 8 }}>
        {angles.map((a, i) => (
          <button key={a.id} onClick={() => switchAngle(i)}
                  style={{ fontWeight: i === active ? "bold" : "normal" }}>{a.label}</button>
        ))}
      </div>
      <input value={angles[active].label} onChange={(e) => renameAngle(active, e.target.value)} />
      <button disabled={angles.length === 1} onClick={() => removeAngle(active)}>Remove angle</button>
      <label> Add angle:
        <input type="file" accept="image/png,image/jpeg" onChange={(e) => {
          const f = e.target.files?.[0]; if (f) onAdd(f);
        }} />
      </label>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run (in `web/`): `npm test -- AngleBar` then `npm run build`
Expected: PASS; build clean.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/AngleBar.tsx web/src/components/AngleBar.test.tsx
git commit -m "feat(web): AngleBar — add/switch/rename/remove angles"
```

---

### Task 8: Frontend — assemble the Studio layout + manual parity check

**Files:**
- Modify: `web/src/App.tsx`

**Interfaces:**
- Consumes: `PhotoUploader`, `AngleBar`, `RegionSelector`, `ManagePanel`, `BandControl`, `PreviewImage`, `useAnalyze`, store `angles`.
- Produces: the assembled studio — uploader (pre-first-photo) → angle bar + region selector + canvas/manage + band control + live preview.

- [ ] **Step 1: Assemble the layout**

Replace `web/src/App.tsx`:

```tsx
import { PhotoUploader } from "./components/PhotoUploader";
import { PreviewImage } from "./components/PreviewImage";
import { BandControl } from "./components/BandControl";
import { RegionSelector } from "./components/RegionSelector";
import { ManagePanel } from "./components/ManagePanel";
import { AngleBar } from "./components/AngleBar";
import { useAnalyze } from "./hooks/useAnalyze";
import { useProjectStore } from "./store/projectStore";

export default function App() {
  useAnalyze();
  const hasAngle = useProjectStore((s) => s.angles.length > 0);
  return (
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: 16 }}>
      <h1>Mini Highlight Advisor</h1>
      {!hasAngle ? (
        <PhotoUploader />
      ) : (
        <>
          <AngleBar />
          <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
            <div style={{ flex: "0 0 auto" }}>
              <PreviewImage />
            </div>
            <div style={{ flex: 1 }}>
              <RegionSelector />
              <ManagePanel />
              <BandControl />
            </div>
          </div>
        </>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Run the full frontend suite + build**

Run (in `web/`): `npm test` then `npm run build`
Expected: all tests PASS; `tsc -b && vite build` clean.

- [ ] **Step 3: Manual parity smoke (both processes running)**

Terminal 1: `.venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000`
Terminal 2 (in `web/`): `npm run dev` → open http://localhost:5173

Verify against Streamlit (`streamlit run app.py`, :8501) with the same sample photo:
- Upload a photo → preview appears.
- Draw a lasso region → outline appears in its region colour; preview updates to reflect the region's (neutral) bands.
- Select Whole mini vs the region; the band slider changes the selected region only.
- Toggle a region's visibility off → it drops out of the preview.
- Add a second angle (upload another photo) → switch between angles; each keeps its own regions and preview.
- Rename/delete a region and rename/remove an angle.

- [ ] **Step 4: Commit**

```bash
git add web/src/App.tsx
git commit -m "feat(web): assemble Studio layout (angles + regions + preview)"
```

---

## Self-Review Notes

- **Spec coverage:** §3 store reshape → Task 4; §4.1 regions/analyze → Task 1; §4.2 mask_cache → Task 1; §4.3 photo-image endpoint → Task 2; §5 coordinate invariant/decimation/draft → Tasks 3 + 5; §6 RegionSelector/ManagePanel/AngleBar → Tasks 6 + 7; §7 data flow (per-angle preview, non-blank regions) → Task 4 (`useAnalyze`) + Task 8; §8 error handling → per-angle `error` in Task 4 (`setError`/`PreviewImage`); §9 testing seams → tests in Tasks 1–7 + manual parity in Task 8.
- **Type consistency:** `rings: number[][][]` (TS) / `list[list[tuple[float,float]]]` (py); `RegionPayload` (wire) vs `DrawnRegion` (store, adds `id`/`blank`); `activeAngleOf`/`activeBookOf` used identically across Tasks 4–7; `RegionCanvas` controlled contract `{drawing, draftRings, onDraftChange}` matches its consumer in Task 6.
- **Deferred (correctly out of scope):** per-region palette/ramp editing (ColourPanel), project save/load `points` persistence, i18n strings (English literals used here; the i18n-port slice replaces them).
```
