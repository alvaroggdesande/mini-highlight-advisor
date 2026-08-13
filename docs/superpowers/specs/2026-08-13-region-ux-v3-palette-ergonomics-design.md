# Region UX v3 + Palette Ergonomics

Date: 2026-08-13
Branch: `feat/region-ux-v3-palette-ergonomics`

## Problem

Region UX v2 (PR #10) made regions live, selectable, and editable, but four
day-to-day frictions remain in the Miniature-tab editor (`app.py`):

1. **A region's name is frozen at creation.** It is set once in the draw-mode
   text input (`app.py:256`) and `Region.name` has no editor. Fixing a typo or
   renaming means Delete + redraw.
2. **Only the last lasso survives.** `_points_from_object(objs[-1])`
   (`app.py:263`) keeps a single stroke. A material that appears in scattered
   spots (both pauldrons + a belt) can't be captured as one region in one pass.
3. **You can't read or reproduce a colour.** Custom slots use a `color_picker`
   swatch (`app.py:346`) that never shows its hex as text, and catalogue slots
   don't show hex either. Picking a nice "dark red" visually is intuitive, but
   afterwards you don't know *what* you picked — no hex to record, and the paint
   name is easy to miss — so you can't reproduce it next session or buy the paint.
4. **No way to fill an in-between rung.** With anchor colours in slots 3 and 5,
   there's no quick way to make slot 4 the blend of them; you eyedrop it by hand.

None of these touch the banding / lighting / edge engine. This is a
region-lifecycle + palette-editor UX batch, sitting entirely on the "monochrome,
human-assigns-palettes" side of the tool (see the colored-mini note below).

## Non-goals

- No change to `banding.py` / `lighting.py` / edge rendering.
- No region **reshape** (still Delete + redraw, per Region UX v2's phased plan).
- No colored-mini / albedo work, no auto-segmentation, no LLM.
- "Whole mini" (region 0) stays unrenamable — it is the leftover base layer.

## Why this is not colored-mini (#10)

Regions assign *which paints go where* on a **monochrome** canvas: the primer is
one uniform value, so luminance is pure form and each region's ramp is clean.
Colored-mini instead must *read form on a non-neutral surface*, where brightness
conflates form with albedo (a yellow area is intrinsically brighter than a blue
one) — an intrinsic-decomposition problem needing a spike. This batch lives
wholly on the solved, monochrome side and does not advance #10.

## Design

Four independent sub-features. Each pure helper is unit-tested; UI wiring is
verified manually.

### A. Rename a region

- New method `RegionBook.set_name_at(g, name)`: raises on `g == 0` (Whole mini is
  fixed), else sets `drawn[g-1].name`; a blank/whitespace name is rejected
  (keep the existing name).
- Editor panel (`app.py`, under `### Editing: <name>`), only when `sel >= 1`:
  a `st.text_input("Region name", value=<current>)`. On a changed, non-blank
  value, call `set_name_at` and `st.rerun()` so the radio labels refresh.
- Region 0 shows no rename field.

### B. Multiple lassos → one region (union)

- New helper `regions.polygons_to_mask(list_of_point_lists, shape) -> np.ndarray`:
  OR of `polygon_to_mask` over each point list; empty input → all-False mask.
  `polygon_to_mask` stays as the single-ring primitive it calls.
- In the **Add region** handler (`app.py:258-274`): replace the `objs[-1]` single
  stroke with *all* objects. For each object, `_points_from_object` → scale →
  collect its point list; `polygons_to_mask(all_lists, (src_h, src_w)) &
  shading.mask`. Unchanged: the "didn't overlap the mini" guard, name, palette,
  coverage seeding, draw-mode reset.
- The canvas already records multiple freedraw strokes as separate objects, so no
  canvas-config change — we simply stop discarding all but the last.
- Result: one named region whose mask is the union of every stroke drawn this
  session. (Each stroke is a closed ring via `polygon_to_mask`'s fill.)

### C. Hex visibility + paste + nearest paint

For **every** palette slot, show the hex as readable text next to the slot.

- **Custom slot:** keep the `color_picker` as the primary, intuitive way to pick a
  colour. Add a `st.text_input` to type/paste a hex, validated by new helper
  `palette.valid_hex(s) -> bool` (accepts `#RGB`/`#RRGGBB`, case-insensitive,
  normalises to `#rrggbb`). Picker and text field stay in sync via the shared
  `slot_hex_{i}` session key: a valid pasted hex updates the key (and thus the
  picker) on rerun; an invalid paste is ignored with an inline caption. The
  existing "Closest: <name> · <range> · <code> (owned?)" caption stays and is the
  answer to "which paint is this dark red?".
- **Catalogue slot:** also render its `paint.hex` as text (alongside the existing
  swatch) so the value is recordable.

### D. Interpolate a middle colour from its neighbours

- New helper `palette.blend_hex_lab(h1, h2) -> str`: convert both hexes to CIE-Lab,
  average, convert back to `#rrggbb`. Lab (not raw RGB) so the midpoint is
  perceptually central rather than muddy. Uses the same colour-conversion path
  already available via OpenCV/numpy in the repo; no new dependency.
- Each **interior** slot `i` (`0 < i < n-1`) gets a small
  `st.button("↕ blend neighbours", key=...)`. On click: set `slot_hex_{i}` to
  `blend_hex_lab(slot_hex_{i-1}, slot_hex_{i+1})` — the blend of the two adjacent
  slots; force `slot_code_{i}` to `CUSTOM`; `st.rerun()`.
- End slots (darkest, lightest) have no button — they are the ramp's anchors.

## Data flow

Unchanged end-to-end: edits still write through the widget keys →
`book.set_palette_at` / `set_coverage_at` (and now `set_name_at`) →
`book.analyze_args()` → `analyze_regions(...)`. B changes only how a mask is built
before `book.add`; C and D only change how `slot_hex_{i}` / `slot_code_{i}` are
populated; A adds a name write-back. No render-path change.

## Error handling

- Rename: blank/whitespace rejected, prior name kept.
- Union: zero strokes or no overlap → existing "trace a lasso" / "didn't overlap"
  warnings; nothing added.
- Hex paste: invalid string → ignored, inline caption, picker value unchanged.
- Blend: end slots have no button; interior blend always has two valid neighbour
  hexes, so it cannot fail on well-formed slot state.

## Testing

Unit tests (pytest, `.venv/Scripts/python -m pytest`):

- `polygons_to_mask`: two disjoint triangles → both filled; single ring matches
  `polygon_to_mask`; empty list → all-False.
- `valid_hex`: accepts `#abc` / `#AABBCC`; rejects `xyz` / `#12` / missing `#`;
  normalises to lower `#rrggbb`.
- `blend_hex_lab`: `#000000` + `#ffffff` → a mid grey near `#777`–`#808080`;
  symmetric in argument order; endpoints return themselves.

UI wiring (rename field, multi-stroke Add, hex text/paste, blend buttons) is
smoke-tested manually in `streamlit run app.py` by the user.

## Success criteria

- A drawn region can be renamed in place; the radio and headings update, no
  redraw. Whole mini has no rename field.
- Tracing several lassos then clicking Add region yields one region whose mask
  is their union.
- Every slot shows its hex; a custom slot accepts a pasted hex and keeps the
  picker in sync; the nearest-paint caption still identifies custom colours.
- An interior slot's "blend neighbours" button fills it with the Lab-midpoint of
  its two neighbours as a custom colour.
- No change to banding/lighting/edge output.

## Risks

- **Streamlit picker ↔ text-field sync.** Both bound to one `slot_hex_{i}` key;
  the text field writes the key on change and the picker reads it on rerun. Avoid
  a second widget owning the same key with a conflicting `value=` (the pattern the
  existing code already respects for `n` and `cov_pct_*`).
- **Widget-key GC on rerun** (the hazard called out in `app.py:287-303`). The new
  rename/blend buttons rerun before the editor widgets render, so `set_name_at`
  and the blend write must target the book / `slot_hex_{i}` keys that the existing
  `setdefault` rehydration already restores — no new persistence surface.
