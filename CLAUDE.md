# CLAUDE.md — Mini Highlight Advisor

Guidance for AI agents working in this repo.

## What this is

A tool that turns a photo of a **primed miniature** into a paint-by-layer
highlight plan (painted preview + written guide + paint-along step images).
Streamlit app now; UI-agnostic core so a web app can reuse it later.

## Module map (`src/mini_highlight_advisor/`)

- `masking.py` — `load_image` (returns `rgb, alpha`) and `compute_mask`
  (alpha fast-path; OpenCV GrabCut fallback when there's no alpha channel — no
  model download).
- `lighting.py` — `luminance_light`: CLAHE-enhanced grayscale as the shading map.
- `banding.py` — `band_light`: coverage-controlled curved banding into layers;
  `relief_recommended_bands`: max band count a region's tonal spread honestly
  supports (drives the render-only relief cap for flat regions).
- `palette.py` — `PaintColor`, `DEFAULT_PALETTE`, `role_names`, coverage helpers.
- `overlay.py` — rendering: `paint_preview` (combined panel), `render_legend`,
  `compose_panel`, and `per_band_images` → `BandStep` (the paint-along steps).
- `pipeline.py` — `analyze(rgb, alpha, palette) -> HighlightResult` wires it all;
  `HighlightResult.steps` carries the per-layer `BandStep`s. `analyze_regions`
  is the multi-region render path; its leftover plan is named `WHOLE_MINI`.
- `regions.py` — `Region(name, mask, palette, coverage)` + mask/owner helpers.
- `region_state.py` — `RegionBook`: the editor's live region list (index 0 =
  "Whole mini" leftover region; 1..N = drawn `Region`s), routing palette/coverage
  edits by selected index. Streamlit-free; `app.py` binds widgets to it.
- `osl.py` — object-source lighting: a clicked coloured point light over the PS
  normals (N·L × screen falloff) → glow preview + extra "glaze the glow" steps.
  PS mode only. `pipeline.apply_osl` runs it as a post-process; base plans untouched.
  OSL now lives in the editor's PS-mode **Glow tab** (`ui/osl_panel.py`); the glow
  composites into the main preview via `ui/helpers.build_osl_result`, and its glazing
  steps render in the Paint tab through `results.render_osl_steps`.
- `app.py` (repo root) — the Streamlit UI.

## Core conventions

- `bands`: int array, one layer per masked pixel (a partition). Off-mask = `-1`,
  so `mask == (bands >= 0)`. Band `0` = darkest, `n-1` = lightest.
- Paint colours: `np.ndarray` float32 shape `(3,)`, RGB.
- Step-image rendering: background = greyscale × `_STEP_DIM` (0.4); active zone =
  paint colour at alpha 0.78, or the magenta `_ACCENT` at 0.85 for the zone marker.
  The combined preview uses `_DIM` (0.25) — keep the two dim constants separate.

## Hard constraints (v1)

- **Primed / monochrome minis only** (luminance is the shading signal). Capture
  reality: minis are black/grey primed and often shot with on-axis flash, which
  *flattens* form — a raking side light is strongly preferred (see the shooting
  guide). NOT zenithal-primed; the engine relies on the *lighting*, not a baked-in
  gradient. On-axis flash is the flat-lighting worst case (see the 2026-08-14
  roadmap addendum).
- **Manual regions supported.** "Whole mini" is the default region (owns
  leftover pixels); users lasso extra regions, each with its own editable
  palette + coverage. Region outlines are immutable once drawn (grow-a-region
  and coloured-mini support are later roadmap phases).

## Working here

- Environment: opencv + pillow + numpy + streamlit in `.venv` (py 3.11). (torch +
  transformers were dropped — the mask fallback is OpenCV GrabCut now.)
- Tests: `.venv/Scripts/python -m pytest`. Run the app: `streamlit run app.py`.
- Process: brainstorm → spec (`docs/superpowers/specs/`) → plan
  (`docs/superpowers/plans/`) → subagent-driven implementation. Feature branch +
  PR/merge; never build straight on `main`.

## Web app (React + FastAPI)

A React+Vite frontend and FastAPI backend coexist alongside the Streamlit app.

**Architecture:** Two independent processes:
- Backend (`uvicorn` on :8000): Imports `src/mini_highlight_advisor/` directly to
  provide `/api/photo` (photo + mask upload) and `/api/analyze` (shading plan).
- Frontend (`npm run dev` on :5173): React + TypeScript + Vite, with API proxy
  (`/api` → :8000).

**Shared core:** `src/` is untouched and used by both the backend and Streamlit UI.

**Streamlit coexistence:** Streamlit (`streamlit run app.py` on :8501) continues
to run independently. The React app does not replace it; both are available.

**Getting started:**
1. Install backend deps: `.venv/Scripts/python -m pip install -r backend/requirements.txt`
2. Run backend: `.venv/Scripts/python -m uvicorn backend.main:app --reload --port 8000`
3. Run frontend: `cd web && npm run dev` (opens http://localhost:5173)

See `backend/README.md` and `web/README.md` for test commands and more detail.
