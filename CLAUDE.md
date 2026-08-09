# CLAUDE.md — Mini Highlight Advisor

Guidance for AI agents working in this repo.

## What this is

A tool that turns a photo of a **primed miniature** into a paint-by-layer
highlight plan (painted preview + written guide + paint-along step images).
Streamlit app now; UI-agnostic core so a web app can reuse it later.

## Module map (`src/mini_highlight_advisor/`)

- `masking.py` — `load_image` (returns `rgb, alpha`) and `compute_mask`
  (alpha fast-path; depth-model fallback when there's no alpha channel).
- `lighting.py` — `luminance_light`: CLAHE-enhanced grayscale as the shading map.
- `banding.py` — `band_light`: coverage-controlled curved banding into layers.
- `palette.py` — `PaintColor`, `DEFAULT_PALETTE`, `role_names`, coverage helpers.
- `overlay.py` — rendering: `paint_preview` (combined panel), `render_legend`,
  `compose_panel`, and `per_band_images` → `BandStep` (the paint-along steps).
- `pipeline.py` — `analyze(rgb, alpha, palette) -> HighlightResult` wires it all;
  `HighlightResult.steps` carries the per-layer `BandStep`s.
- `app.py` (repo root) — the Streamlit UI.

## Core conventions

- `bands`: int array, one layer per masked pixel (a partition). Off-mask = `-1`,
  so `mask == (bands >= 0)`. Band `0` = darkest, `n-1` = lightest.
- Paint colours: `np.ndarray` float32 shape `(3,)`, RGB.
- Step-image rendering: background = greyscale × `_STEP_DIM` (0.4); active zone =
  paint colour at alpha 0.78, or the magenta `_ACCENT` at 0.85 for the zone marker.
  The combined preview uses `_DIM` (0.25) — keep the two dim constants separate.

## Hard constraints (v1)

- **Primed / monochrome minis only** (luminance is the shading signal).
- **Whole mini as one region.** Both lift in later roadmap phases
  (per-material regions, coloured-mini support).

## Working here

- Environment: CPU torch + transformers + opencv + streamlit in `.venv` (py 3.11).
- Tests: `.venv/Scripts/python -m pytest`. Run the app: `streamlit run app.py`.
- Process: brainstorm → spec (`docs/superpowers/specs/`) → plan
  (`docs/superpowers/plans/`) → subagent-driven implementation. Feature branch +
  PR/merge; never build straight on `main`.
