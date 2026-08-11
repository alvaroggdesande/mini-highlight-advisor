# Manual Region Lasso — Design

**Date:** 2026-08-11
**Status:** Approved design, ready for implementation plan.
**Predecessor:** `2026-08-09-roadmap-and-idea-assessment.md` (idea #1, per-material
regions; SAM ruled out; manual lasso is the chosen path).

## Purpose

Let the painter divide a mini into **multiple regions** (robe, blade, base…), give
each region its **own palette and band settings**, and see the results **combined**
into one plan — plus a descriptive board that shows every region's colour scheme at
once. This is the "hub enabler" from the roadmap: it unsticks per-region techniques,
edge-highlight-as-separation, and coloured-mini work later.

The engine's core premise is preserved: **the lasso only assigns *which paints* apply
to an area; it does NOT place the highlights — luminance does.** Each band (including
the edge highlight) is the brightest-quantile of luminance *within* a region's mask.

## Scope decisions (locked during brainstorming)

- **Region/background model = C.** The app keeps a **global default palette** (today's
  behaviour). With **zero regions drawn, output is identical to today** (single-region
  path). Regions are additive overrides on top of the default.
- **Per-region config depth = B.** Each region carries its own **palette + band count
  + coverage**, each defaulting to the global settings. Technique presets (per-region
  NMM / OSL curves) are a **future feature (C)**, out of scope here.
- **Colour-schema check = A.** A **descriptive swatch board** only — all regions'
  palettes side by side. No harmony judgement. Structured so a lightweight harmony
  readout (B: warm/cool balance, near-duplicate flag, value spread) is a trivial
  additive computation later.
- **Drawing mechanism = A with a spike, B as fallback.** Use
  `streamlit-drawable-canvas` for true freehand/polygon lasso. **Gate it behind a
  spike** confirming it runs on the repo's pinned Streamlit. If the spike fails, fall
  back to `streamlit-image-coordinates` polygon-clicking — the downstream mask code is
  identical either way.

## Region/background semantics

- A **region** is `{ name, mask, palette, n_bands, coverage }`. Regions are stored as
  an **ordered list**.
- **Pixel assignment is exclusive and last-wins:** for each on-mask pixel, the *last*
  region (in list order) whose lasso covers it owns that pixel. Pixels no region
  covers fall to the **global default palette**. Drawing a correction on top just
  works (it's last).
- No feathering / edge-snapping in v1 — exclusive hard boundaries. The roadmap's
  feather / edge-snap / refine-brush seam mitigations stay **parked** for a later
  refinement pass.

## Drawing flow

1. User uploads the mini photo (as today); it renders inside a drawing canvas sized to
   the displayed image.
2. User draws a lasso, types a **region name**, picks a **palette** (reusing the
   existing editable-palette + own-palette UI), sets **band count / coverage**. Clicks
   **"Add region."**
3. Rasterise the canvas path → boolean mask; **scale from display resolution back to
   source-image resolution**; **intersect with the existing mini mask** so a region can
   never spill off-sculpt.
4. Regions list renders below, each **removable**. Re-running re-renders everything.

## Pipeline changes

- Banding runs **per region, within that region's sub-mask**. Each region's luminance
  is quantile-banded independently, so every region (incl. its edge highlight) is the
  brightest-quantile *within itself*. A dark blade and a bright robe each get a full
  tonal range; no region is starved by a brighter neighbour.
- `analyze()` generalises from "one palette over the whole mask" to: build the
  exclusive last-wins assignment (default region = leftover pixels), band each region
  within its sub-mask, composite. Because assignment is exclusive, the composited
  `bands` array remains a clean partition (`-1` off-region), so existing
  overlay/step-image code works unchanged when fed per-region sub-masks.
- Per-band step images and legends are generated per region, then **grouped under each
  region's name**.

## Outputs

- **Combined overlay** — one final painted preview; every region shows its own palette,
  composited by the last-wins mask. The "see it all together" view.
- **Per-region step images** — existing paint-along steps, grouped under region headers.
- **Swatch board** — one panel listing each region: name + its palette swatches in band
  order, stacked so all schemes are visible at once. Pure display. Implemented as a
  small `swatch_board(list[Region])` in `overlay.py`, structured so harmony readout (B)
  is additive.

## Testing

- **Unit:** mask rasterisation + display→source scaling; exclusive last-wins
  compositing (overlapping regions resolve correctly); per-region banding yields a valid
  partition with `-1` off-region.
- **Zero-region regression:** identical output to today's single-palette path (guards
  model C).
- The canvas component is validated by the **spike**, not unit tests (UI dependency).

## Out of scope (this build)

- Feathered / edge-snapped / refine-brush seams.
- Per-region technique presets (future C — NMM / OSL curves).
- Harmony *judgement* (swatch board is descriptive only; readout B is later).
- Auto region detection (SAM ruled out in the roadmap spike).

## Risk & de-risking

- **Primary risk:** `streamlit-drawable-canvas` compatibility with the repo's pinned
  Streamlit (component is mature but unmaintained). **Mitigation:** `spikes/canvas_spike.py`
  gates the build; `streamlit-image-coordinates` polygon fallback if it fails.
- **Secondary:** display↔source coordinate scaling correctness → covered by unit tests.
