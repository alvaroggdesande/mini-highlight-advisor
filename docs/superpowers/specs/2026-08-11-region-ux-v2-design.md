# Region UX v2 — editable, selectable regions

Date: 2026-08-11
Branch: `feat/region-ux-v2`

## Problem

The current Miniature tab flow is inverted and its regions are frozen. Concretely
(`app.py`, `regions.py`):

1. **Inverted flow.** Palette and coverage are configured *before* the photo is
   uploaded (upload is near the bottom of the tab, `app.py:282`) and before any
   region is drawn.
2. **Regions are snapshots, not objects.** `Region(name, mask, list(palette),
   list(coverage))` copies the global palette/coverage at "Add region" time
   (`app.py:316`). After that there is **no way to edit a region's colours or
   coverage** — you must Remove the region, redraw the lasso, and rebuild it.
3. **One palette editor does two jobs** — the whole-mini plan *and* a scratch
   buffer snapshotted into regions.

The user's ask: add image → draw regions if needed → choose palettes/recipes →
**come back to any region and change its colours and coverage**, and make edits
easier and more intuitive.

## Core decision

The fix is a **data-model change**, not a widget rearrangement: a `Region`
becomes a **live, editable, selectable** object that owns its own palette and
coverage. Once that is true, "revisit any region and change it" falls out for
free.

## Design

### 1. Model: Region as a live object; "Whole mini" is region 0

- **"Whole mini" is always the default region (index 0)** and owns every masked
  pixel not claimed by a later-drawn region. There is no "no regions" special
  case anymore.
- `analyze_regions` becomes the **only** render path. The standalone
  `band_and_render` single-plan branch in `app.py` is removed (the function may
  stay as an internal building block if `analyze_regions` uses it).
- A region's `palette` and `coverage` are edited **in place**, keyed by
  `st.session_state["selected_region"]`. No snapshotting on add.
- Region ownership/overlap stays **last-wins by list order** (`assign_owners`
  unchanged); "Whole mini" is the base layer, drawn regions layer on top.

### 2. Layout & interaction

Single Miniature tab, top to bottom:

- **Upload** moves to the **top**.
- Two columns beneath it:
  - **Left:** preview image with coloured region outlines drawn on it
    (read-only — no click-to-select).
  - **Right:** a **region list** (radio) — `● Whole mini / ○ Cloak / …` — plus a
    `[+ Draw new region]` toggle that reveals the lasso canvas. Selection happens
    **in the list**, never by clicking the image (avoids drawable-canvas hit
    detection).
- **Full-width below:** combined painted preview + per-region paint-along steps
  (existing `analyze_regions` render output).

### 3. New-region defaults + editor panel

Finishing a lasso creates a region with a neutral default ramp and **auto-selects
it**. Drawing never blocks with a modal.

The editor panel acts on the **selected region** and shows, in order:

1. **Recipe picker** — fills the palette slots. Front-and-centre.
2. **Palette slots** — layer count + colour per layer.
3. **Coverage sliders** — remainder model, unchanged.
4. **Match to my paints** — scoped to *this region's* palette.
5. **Save as recipe** — saves *this region's* palette.

The panel is identical whether the region is brand-new or being revisited — one
mental model. "Match to my paints" and "Save as recipe" stop being global blocks
and become per-region.

### 4. Shape editing (phased)

- **v1: outline is immutable.** Reshape = Delete region + draw a new lasso.
  Colours/coverage remain editable forever.
- Region model and canvas plumbing are built so a future **v2 "add stroke →
  union into the selected region"** (grow a region) is additive, not a rewrite.
- **Full vertex editing is out of scope** — not worth fighting drawable-canvas
  for a personal tool.

### 5. Out of scope / unchanged

- **Paints tab** unchanged.
- **Banding / lighting / step-image rendering core** untouched. This is a UI +
  `Region` lifecycle change, not an algorithm change.
- No coloured-mini or SAM-mask work here.

## Success criteria

- Upload is the first action in the Miniature tab.
- "Whole mini" region always exists and owns leftover pixels; removing all drawn
  regions leaves a valid whole-mini plan.
- Selecting a region in the list loads its palette/coverage into the editor;
  changing a colour or coverage slider updates *that* region and re-renders,
  with no need to delete/redraw.
- Drawing a new lasso creates and selects a neutral region without a blocking
  prompt.
- Match-to-paints and Save-as-recipe operate on the selected region.
- Deleting a region returns its pixels to whichever region previously owned them
  (ultimately "Whole mini").

## Risks

- **Streamlit rerun + drawable-canvas state.** Mitigated by list-based selection
  (not canvas clicks) and keying the canvas so a completed lasso is consumed once
  into a region then reset.
- **Editor ↔ session_state binding.** Each region's palette/coverage must be
  stored on the `Region` and loaded into widget keys on selection change, not
  held only in widget keys (which caused the snapshot coupling originally).
