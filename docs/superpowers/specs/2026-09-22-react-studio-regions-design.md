# Studio Regions Slice — Design Spec

- **Date:** 2026-09-22
- **Status:** Approved (design) — pending implementation plan
- **Owner:** Alvaro
- **Branch:** `feat/react-studio-regions`
- **Parent spec:** `2026-09-22-react-fastapi-migration-design.md` (§7 component map,
  §10 rollout, §14 risks). This slice is the first feature after Phase 0.

## 1. Scope

The second slice of the React + FastAPI migration, immediately after the Phase 0
vertical slice (upload → live preview). It delivers the **Studio regions** layer
**and** the **multi-angle** layer in one slice (decided during brainstorming —
including AngleBar as briefed, so the store is reshaped to `angles[]` once rather
than twice):

- **Backend:** `/api/analyze` accepts `regions`; add a `mask_cache`; add a
  photo-image endpoint for the canvas background.
- **Frontend:** reshape the Zustand store from flat/single-angle to the
  manifest-shaped `angles[] → book:{whole, drawn[]}`; build `RegionCanvas`
  (react-konva), `RegionSelector`, `ManagePanel`, and `AngleBar`.

### In scope
- Draw lasso regions on the active angle's photo (freehand, faithful to Streamlit).
- Select the active region; toggle region visibility (`blank`).
- Manage the selected region: rename, delete.
- Multi-angle: add (upload a photo), switch, rename, remove angles — each angle
  owns its own photo + region book + settings.
- Wire regions into `/api/analyze` so the live preview reflects them.

### Out of scope (their own later slices)
- **ColourPanel** — per-region palette / ramp / paint-picker editing. New regions
  seed a neutral ramp here; real ramp editing is the next slice.
- **Paint steps, Paints inventory, Angles gallery, Schemes, project save/load,
  i18n port, Capture guide.**
- **Project save/load serialization** — `projects.py` is untouched this slice; the
  `points`/`rings` field lives only in the in-memory store. The v5→v6 on-disk
  bump belongs to the save/load slice.
- PS / OSL / NMM (cut from the React app entirely per the parent spec).

## 2. Decisions locked in brainstorming

| Decision | Choice | Rationale |
|---|---|---|
| Slice scope | **Regions + AngleBar together** | Reshape the store to `angles[]` once; matches the brief and the parent spec's §6 manifest shape. |
| Lasso interaction | **Freehand lasso (faithful)** | Matches Streamlit `freedraw`; §11 "faithful port first". Multiple strokes union into one region. Decimate the dense path before storing. |
| Outlines & selection | **Client-side konva vectors** over a raw-photo background | Point-lists live on the client (v6); selecting/hovering redraws zero server images. `region_outline_image` / `highlight_region_image` are **not** ported. |
| Canvas background source | **New `GET /api/photo/{photo_id}/image`** | Uniform by `photo_id`; works for uploads + samples + future project-load; survives reload; no per-angle object-URL bookkeeping. |
| Region geometry shape | **`rings` (list of rings)**, not a single ring | Honours the faithful multi-stroke union (`polygons_to_mask`). Refines parent §6's "list of `[x,y]`" — a legacy single ring wraps as a one-element list. |
| New-region palette | **Neutral gray ramp + even coverage**, client-side | ColourPanel (next slice) owns real ramps; a neutral seed keeps analyze rendering correctly in the meantime. |

## 3. Store reshape (Zustand): flat → manifest-shaped

Phase 0 shipped a flat store (`photoId` / `whole` / `settings` at the top level).
This slice reshapes it to the manifest nesting from the parent spec's §6:

```ts
projectStore = { activeAngle: number; angles: Angle[] }

Angle = {
  id: string;                 // stable key (canvas keying, react keys)
  label: string;
  photoId?: string; width?: number; height?: number;
  qualityChecks: QualityCheck[];
  book: { whole: Whole; drawn: DrawnRegion[]; selected: number };  // selected: 0 = whole, 1..N = drawn
  settings: Settings;
  preview?: string; resultToken?: string; error?: string;         // per-angle
}

DrawnRegion = {
  id: string;
  name: string;
  rings: number[][][];        // IMAGE-space point rings — source of truth, travels over HTTP
  palette: PaintColor[];
  coverage: number[];
  material: string;           // "matte" this slice
  blank: boolean;             // visibility toggle; blank => skipped in analyze
}
```

- **`paints_pool` and `schemes[]` are omitted** — YAGNI; their slices add them.
- **Actions mirror `RegionBook`** (index 0 = whole, 1..N = drawn):
  - Region: `addRegion(rings)`, `removeRegion(g)`, `renameRegion(g, name)`,
    `setSelected(g)`, `toggleBlank(g)`.
  - Angle: `addAngle(photo)`, `switchAngle(i)`, `renameAngle(i, label)`,
    `removeAngle(i)`.
  - Band/coverage edits **route to `book.selected`** — the direct analogue of
    `RegionBook.set_coverage_at(sel)`. The existing `BandControl` keeps working and
    gains per-region routing for free.
- **Existing components rewire** (`PhotoUploader`, `BandControl`, `PreviewImage`,
  `useAnalyze`) to read the active angle's book instead of top-level fields.
- **New drawn regions** seed a neutral gray ramp (`{name:"band", hex:"#808080"}`)
  + even coverage client-side, matching the current `setBandCount` fill.

### Selectors / helpers
- `activeAngle()`, `activeBook()`, `regionNames()` (`⬜ Whole mini` + drawn names),
  `selectedIndex`.
- Angle switch is plain state (`activeAngle = i`); each angle retains its own
  `preview` / `resultToken`, so switching shows the last preview instantly.

## 4. Backend changes

### 4.1 `/api/analyze` accepts regions
- `AnalyzeRequest` gains `regions: list[RegionModel] = []`:
  ```py
  class RegionModel(BaseModel):
      name: str
      rings: list[list[tuple[float, float]]]   # image-space rings
      palette: list[PaintColorModel]
      coverage: list[float]
      material: str = "matte"
  ```
- For each region: `mask = polygons_to_mask(rings, (h, w)) & shading.mask`, build
  `Region(name, mask, palette, coverage, material)`, pass the list as
  `analyze_regions(..., regions=regions)`. Blank regions are filtered client-side
  (not sent), matching `RegionBook.analyze_args`.
- The existing analyze token hashes `model_dump_json()`, which now includes
  `regions` — so the token varies with regions automatically (no change needed).

### 4.2 `mask_cache` (parent §14)
- New bounded LRU in `backend/main.py`: `(photo_id, sha256(rings_json)) → bool mask`.
  Immutable region outlines rasterize once. Keyed on the rings so identical
  outlines across edits/reanalyses hit the cache.

### 4.3 Photo-image endpoint (canvas background)
- `GET /api/photo/{photo_id}/image` → the cached `rgb` as `image/png`.
  Returns 404 if the photo has been evicted from `shading_cache` (client
  re-uploads). Reuses `serialize`/PIL; no core change.

## 5. RegionCanvas & the coordinate invariant (parent §14)

The one subtle correctness invariant. Rules:

- **Display size identical to Streamlit**, so behaviour matches exactly:
  `dispW = min(600, srcW)`, `dispH = round(srcH * dispW / srcW)`.
- Konva `Stage` sized `dispW × dispH`; background `Konva.Image` (from
  `/api/photo/{id}/image`) scaled to fit the stage.
- **Capture** freehand pointer points in **display coordinates**.
- **On commit, scale to image space**:
  `sx = srcW / dispW`, `sy = srcH / dispH`; `imgPt = [x * sx, y * sy]`.
  This is exactly `regions.scale_points(pts, srcW/dispW, srcH/dispH)`.
  **Points persist and travel in image space; only rendering scales
  display ↔ image.** The server rasterizes with the same `polygons_to_mask` in
  image space, so masks land correctly.
- **Render existing outlines** by the inverse scale (`x / sx`, `y / sy`) as closed
  konva `Line`s in `REGION_COLORS`. Selected region drawn emphasised (thicker /
  brighter line); non-selected optionally dimmed.
- **Decimation:** Douglas–Peucker at ~1.5px image-space epsilon before storing —
  small payloads, identical interaction. (Improvement over Streamlit, which sent
  every fabric path point; not a UX change.)
- **Draft strokes** live in local component / `uiStore` state, not the book:
  "Add" (with a name) commits `rings → addRegion`; "Cancel" discards. Mirrors the
  Streamlit `draw_mode` → Add/Cancel flow.
- **Canvas keying:** `key={angle.id}` resets in-progress drafts on angle switch.
  The Streamlit `canvas(angle_idx, len(drawn))` stroke-leak hack is unnecessary —
  each angle's book is already independent React state.
- `REGION_COLORS` / `REGION_EMOJIS` / `WHOLE_MINI_EMOJI` port to a shared TS
  constants module (same values as `ui/geometry.py`).

## 6. RegionSelector · ManagePanel · AngleBar

- **RegionSelector** — persistent, above the tabs (as in Streamlit): a radio built
  from `regionNames()` (`⬜ Whole mini`, `🟣 name`, `🔵 name`, …) that sets
  `book.selected`. Per-region visibility = the `blank` toggle; blank regions are
  omitted from analyze.
- **ManagePanel** ← `ui/regions_panel.render_management`: draw toggle, new-region
  name input, Add / Cancel; for the selected drawn region, rename + delete.
  Rename / delete / blank mutate the book → `useAnalyze` refires.
- **AngleBar** ← `ui/angles_panel.py`: switch active angle (plain `setActiveAngle`),
  rename the active angle, remove (disabled at 1 angle), and add via photo upload
  (POST `/api/photo` → new angle with a fresh book, inheriting the current
  settings). All the `_angle_select_target` / `_add_angle_nonce` /
  `_clear_angle_label_keys` Streamlit choreography disappears — plain state.

## 7. Data flow (one edit cycle)

1. User draws / edits a region or scrubs a slider → mutates the **active angle's**
   book (region rings, or `book.whole` / selected-region coverage) or settings.
2. `useAnalyze` (debounced ~150ms) POSTs `/api/analyze` with
   `{photo_id, whole, regions: non-blank drawn (rings/palette/coverage/material),
   settings}`.
3. Server: shading cache hit → mask cache hit/rasterize → `analyze_regions` →
   memoize by token → serialize combined preview → `{preview_png, result_token}`.
4. Client stores `preview`/`resultToken` **on the active angle** and swaps the
   preview image. Switching angles shows that angle's last preview instantly and
   re-analyzes only if its inputs changed.

## 8. Error handling (parent §9)

- Analyze 4xx/5xx → set the active angle's `error`, keep the previous preview in
  place (inline banner, replacing `st.error`).
- Unknown `photo_id` (404 from analyze or the image endpoint) → prompt re-upload of
  that angle's photo.
- Konva background image load failure → inline canvas error; drawing disabled until
  the photo resolves.

## 9. Testing (light; the seams that carry risk — parent §12)

- **Store:** region index-routing (`add` / `remove` / `rename` / `blank` / `setSelected`
  map to the right slot); band/coverage edits route to `book.selected`; **angle
  isolation** (edits to angle A never leak to angle B; switching preserves each
  angle's preview/book).
- **Coordinate scaling:** pure `toImageSpace` / `toDisplaySpace` functions
  round-trip (`display → image → display ≈ identity`) and a known point maps
  correctly for `dispW = min(600, srcW)`; matches the `scale_points` convention.
- **Decimation:** reduces point count while preserving the closed-ring shape within
  epsilon.
- **API client:** analyze request includes `regions`; photo-image URL builder.
- **Backend:** `/api/analyze` with regions builds masks intersected with
  `shading.mask`; `mask_cache` hit on identical rings; token varies with regions;
  `GET /api/photo/{id}/image` returns PNG and 404 on eviction.
- **Konva capture:** a light React Testing Library test that a drag yields
  image-space points (konva may be stubbed).
- **Manual parity vs Streamlit:** same project, same lasso → previews and region
  outlines match.

## 10. Risks & notes

- **Coordinate scaling** is the flagged risk (parent §14) — mitigated by pinning
  `dispW = min(600, srcW)` and unit-testing the scale functions against
  `scale_points`.
- **konva bundle size / SSR** — none; SPA only, dev + single-origin prod already
  established in Phase 0.
- **mask_cache growth** — bounded LRU; single-user localhost, small.
- **New-region neutral ramp** looks plain until ColourPanel — acceptable and
  explicitly deferred.
- **Legacy (v5) mask-only regions** are a save/load-slice concern, not here.

## 11. Rollout

- One feature branch (`feat/react-studio-regions`) + PR; never main (repo rule).
- Decomposed by the writing-plans step into tasks (backend regions + cache +
  image endpoint → store reshape → RegionCanvas → RegionSelector/ManagePanel →
  AngleBar → analyze wiring → tests). Streamlit stays fully runnable throughout.
