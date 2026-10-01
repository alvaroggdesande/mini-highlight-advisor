# UI pass A — fixes and quick wins

Date: 2026-10-01 · Branch: `feat/ui-pass-a-fixes` · Status: draft for review

## Context

A UX review of the React web app (first-time hobbyist lens) produced a list of issues,
split into three pieces shipped separately: **A (this spec) fixes + quick wins**,
B guidance/onboarding, C Studio restructure. A is the low-risk, high-value batch:
real bugs, missing feedback, and the paint-along steps not saying which paint to use.

**Goal:** after A, nothing in the app fails silently, every step card names its paint,
the step images are self-explanatory, and the Spanish UI has no English leftovers.

**Out of scope:** Studio layout/order and jargon renames (piece C), intro / photo tips /
quality warnings / "next step" CTA (piece B), banding/light logic
(`docs/ideas/layer-spread.md`).

## 1. Bugs

| # | Bug | Fix |
|---|---|---|
| 1.1 | "Owned paints only" sends every catalogue code (`colour/GeneratePanel.tsx:32` maps `catalogPaints`). | Use `useCatalogStore(s => s.ownedCodes)` → `Array.from(ownedCodes)`. If the toggle is on and the user owns no paints, show a short hint ("Mark paints you own in the Paint Collection tab") and send `[]`. |
| 1.2 | A band card's ✕ always deletes the **last** band (`colour/BandCard.tsx:66` calls `setBandCount(n - 1)`). | New store action `removeBand(i)`: drop `palette[i]` and `coverage[i]` of the selected region, renormalise coverage to sum 1, no-op when `n <= 3` (current minimum). Call `snapshotUndo()` first, matching how other palette edits are undoable. BandCard calls `removeBand(i)`. |
| 1.3 | Importing a collection from Studio doesn't update the Paint Collection checklist (`colour/RecipeManager.tsx:34`). | Call `setOwnedFromImport(res.owned)` like `PaintsTab.tsx:28`. Recipe + collection import/export there also gain try/catch with a small success/error message (same pattern as PaintsTab). |
| 1.4 | "+ angle" uploads the full-size photo (`AngleBar.tsx:17`). | `uploadPhoto(await downscaleImage(file), file.name)`, same as the first upload. |

## 2. Paint name on each step card

The step cards show only the role ("Highlight"). The paint is the key information
of a paint-along, so each card header becomes:

`[swatch] Highlight — Ivory · Vallejo 70.918`

**Backend** (`backend/schemas.py`, `backend/main.py::_plan_to_dto`): `StepImageDto`
gains three optional fields, `paint_name`, `paint_hex`, `paint_code` (default `None`,
so older clients are unaffected). They are resolved from `plan.palette` — the
*final* palette after relief capping, which the frontend store cannot know:

- band step `k` → `plan.palette[k]`
- edge steps: if the plan has two edge steps (two-tier), the first → `palette[-2]`,
  the second → `palette[-1]`; a single edge step → `palette[-1]` (mirrors
  `edge_steps` / `plan_region`)
- shade / anything else → fields stay `None` (shade steps are PS-only, not in the web app)

**Frontend** (`StepList.tsx`): header shows swatch + role + paint name, plus brand/code
when present. Fields missing → current header unchanged.

## 3. Explain the step images

Today the three images are captioned "Where to paint / Result so far / This layer" with
no explanation. "Result so far" is also misleading: it paints this colour over **every
band ≥ k** (the area this layer covers before later layers go on top), and "This layer"
is only what stays visible at the end.

- Rename captions (EN / ES):
  - `step_zone`: "Where to paint" / "Dónde pintar" (unchanged)
  - `step_cumulative`: "After this layer" / "Tras esta capa"
  - `step_exact`: "What stays visible at the end" / "Lo que queda visible al final"
- One hint line at the top of the step list (`paint.steps_hint`):
  "Each layer is painted over the pink area. Later, lighter layers go on top of it, so
  only part of each layer stays visible at the end." / ES equivalent.

## 4. Loading and error states

Shared pattern: a friendly translated message + **Retry** button + the raw error
detail in small dimmed text (useful for bug reports). A small `ErrorNotice` component
(`components/ErrorNotice.tsx`: `message`, `detail?`, `onRetry?`) is used everywhere below.

| Where | Today | After |
|---|---|---|
| Paint tab, loading regions/steps (`PaintTab.tsx:105,119`) | Bare spinner | Spinner + `paint.loading` ("Loading steps… the first time can take up to a minute") |
| Paint tab error (`PaintTab.tsx:106`) | Red raw string | `ErrorNotice` + Retry (clears error; refetches manifest or the active region's steps) |
| Preview while re-rendering (`useAnalyze.ts`, `PreviewImage.tsx`) | Old image, no signal | Angle gets `analyzing: boolean` (set by `useAnalyze` around the request). A small "Updating preview…" badge + loader shows over the image; first render (no preview yet) shows a centred loader instead of "Upload a photo…" |
| Preview error (`PreviewImage.tsx:6`) | "Analyze failed: 500 …" | `ErrorNotice` + Retry. Retry bumps an `analyzeNonce` on the angle, which is a dependency of the `useAnalyze` effect |
| Upload (`PhotoUploader.tsx`) | No busy state; errors before an angle exists are lost (`setError` patches a missing angle) | Button `loading` while downscaling/uploading; local error state rendered with `ErrorNotice` (no retry — user re-picks the file) |
| Generate (`colour/GeneratePanel.tsx:37-49`) | `try/finally`, failures silent | Add `catch` → `ErrorNotice` under the button |
| Catalogue load (`PaintInventory.tsx:14`) | `status === "error"` spins forever | Error branch with `ErrorNotice` + Retry calling `fetch()` (its guard already allows a retry from `"error"`) |
| Project actions (`ProjectLibrary.tsx`) | English fallbacks "save failed" etc. | Translated fallbacks |

## 5. i18n leftovers

Move hard-coded English into `en.json` + `es.json`:

- `PhotoUploader.tsx`: "Upload photo", "Or start from a sample:"
- `PreviewImage.tsx`: placeholder, "Analyze failed", alt "painted preview"
- `ManagePanel.tsx`: "Draw region", "Add region", "Cancel", "{n} stroke(s)" (plural), "visible", "Delete region"
- `AngleBar.tsx` / `AngleGallery.tsx`: "+ angle", "Rename angle", "Remove angle"
- `colour/BandCard.tsx:20`: "Buy: {name}"
- `colour/GeneratePanel.tsx`: "Whole Mini" **display label only** — the value sent to
  `/api/scheme/generate` as `region_name` / `anchor_name` stays `"Whole Mini"` (it is an identifier)
- `ProjectLibrary.tsx`: the five "… failed" fallbacks
- `RegionHeader.tsx`, `GeneratePanel.tsx`: remaining English `aria-label`s
- New angles are labelled via i18n at creation time: "Angle 1" / "Ángulo 1"
  (capitalised; still user-renamable data, existing projects keep their labels)
- `paints.heading` contains literal markdown "## 🎨 Paints" → plain "Paints" / "Pinturas"

## 6. Testing

- **Backend:** `backend/tests/test_steps.py` — step DTOs carry `paint_name/hex/code`
  matching the plan palette for band steps; edge-step mapping for one-tier and
  two-tier; shade/missing → `None`.
- **Frontend (vitest):**
  - `removeBand(i)` removes the right slot and renormalises; no-op at 3 bands; BandCard ✕ calls it with its own index
  - GeneratePanel sends owned codes only (and `[]` with none owned)
  - RecipeManager collection import updates `catalogStore`
  - AngleBar downscales before upload
  - StepList renders paint name + swatch when present, plain header when absent; the hint renders
  - ErrorNotice renders message/detail and calls `onRetry`
  - PaintTab / PreviewImage / PaintInventory error branches show Retry
  - es locale: every key in `en.json` exists in `es.json` (parity test, if not already present)
- Existing tests updated where captions/labels changed.

## 7. Risks

- `analyzing` / `analyzeNonce` are runtime-only angle fields. Saving goes through the
  explicit field mapping `toProjectAngleDto` (`api/client.ts`), so they cannot leak into
  project JSON; `initFromProject` must default them (`false` / `0`).
- The DTO change is additive and optional → no versioning needed.
