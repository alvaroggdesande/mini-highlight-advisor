# OSL — reshape into a toggleable "Glow" layer (UI + paint-guide)

**Date:** 2026-09-04
**Status:** Approved design — ready for implementation plan.
**Branch:** `feat/osl-object-source-lighting` (continues the OSL feature; glow math already merged on this branch)

## What this is

The OSL feature works, but three UX problems and one guide gap surfaced in use:

1. The click-to-place canvas is **blank** — the user clicks on an empty rectangle,
   guessing where the mini is, because the canvas has no background image.
2. The glow preview renders as a **second, duplicate image tacked on below** the
   whole editor instead of showing in the main preview.
3. OSL is a standalone panel, not a **toggleable layer** that feels part of the editor.
4. The paint-along steps for the glow **don't teach the technique** — they print a
   paint name and "after this layer" with no glazing guidance, so a user who hasn't
   painted OSL before doesn't know what to actually do.

This spec reshapes OSL from a below-the-editor panel into a first-class **"Glow"
tab inside the shared editor**, composites the glow into the **main preview**, fixes
the placement canvas to show the mini, and enriches the glow-step captions with real
glazing guidance.

**This is a UI-layer reshape plus a caption change. The glow math is untouched:**
`osl.py`, `pipeline.apply_osl`, region plans, and the persistence format are all
byte-identical after this change.

## Decisions locked in brainstorming (2026-09-04)

1. **Full reshape**, not incremental quick-wins — fixes all four points in one pass.
2. **"Glow" tab in the editor** (a 4th tab beside Manage / Colour / Technique),
   PS-mode only. Not a pinned strip, not a below-editor panel.
3. **OSL is an overlay layer, NOT a `RegionBook` region.** Regions own pixels
   exclusively (the "Whole mini" region owns leftovers) and carry a palette; OSL is a
   post-process glow driven by a point + the normals that sits on top of every region.
   Modelling it as a literal `Region` would be a category error. The enable checkbox
   is the on/off toggle the user asked for; it does not join the region partition.
4. **Live apply** (keep current behaviour): the glow re-derives every rerun from the
   session-state params. The enable toggle is the gate — no separate "Add glow steps"
   button (the old OSL spec mentioned one; it was never built and we don't want it).

## The ordering problem (load-bearing)

`editor.render` (`ui/editor.py`) draws the main preview (`multi.combined_rgb`) near
the top (line ~46), **before** the tabs are rendered (line ~85). OSL controls live in
a tab, so on the run where the user changes them the preview has already drawn.

The editor **already solves exactly this** for the region visibility toggles: it
pre-syncs toggle state from `session_state` into the book *before* analysis (lines
27–34), with a comment explaining that the toggles render later in `col_controls` so
without the pre-sync "the preview would always be one rerun behind the toggles."

OSL reuses that pattern: the Glow tab widgets write params into `session_state`;
`editor.render` reads those params **up front** (before drawing the preview) and
composites the glow onto `combined_rgb`. Streamlit reruns on every interaction, so the
preview stays in sync with the controls without an extra rerun — identical to how the
visibility toggles already behave.

## Architecture / where code moves

### `ui/editor.py` — gains the glow layer

- **Pre-preview composite.** Before `st.image(multi.combined_rgb, …)`, add: if
  `normal_field is not None` and OSL is enabled (`keys.OSL_ON`) and a source point is
  placed (`keys.OSL_POINT`), read the OSL params from `session_state`, compute the
  glow contribution, and screen-composite it onto the image that gets displayed. When
  disabled or unplaced, display `combined_rgb` unchanged.
- **Glow tab.** Change `st.tabs([...])` to append a 4th tab **only when
  `has_normals`** (so photo mode still shows exactly three tabs). The tab body calls
  `osl_panel.render(...)`.
- **Store the result.** Put the computed `OslResult` (or `None`) into
  `st.session_state[keys.OSL_RESULT]` so the Paint tab renders its steps, exactly as
  `ps_mode` does today.

The composite + step generation should live in a small helper (e.g.
`ui/helpers.py: build_osl_result(...)` or a private function in `editor.py`) that takes
`(combined_rgb, normals, mask, params, owned, catalog)` and returns `(preview_rgb,
OslResult)`, so `editor.render` stays readable and the logic is unit-testable without
Streamlit. It wraps the existing `pipeline.apply_osl` — no new glow math.

### `ui/osl_panel.py` — becomes the Glow-tab body, canvas fixed

- Signature gains the current preview image so the click canvas has a background:
  `render(mask_shape, background_rgb) -> dict | None` (or pass the whole context it
  needs). The blank `st_canvas(height=h, width=w, drawing_mode="point", …)` becomes a
  canvas with `background_image=Image.fromarray(background_rgb)` at **display scale**
  (`disp_w = min(600, w)`, `disp_h` proportional), mirroring `regions_panel.py`.
- Because the canvas is now scaled, the returned click must be **scaled back to full
  mask resolution** (`sx = src_w / disp_w`, `sy = src_h / disp_h`) before it becomes
  `params["x"], params["y"]`, so the glow lands where the user clicked. This mirrors
  the `scale_points` step in `regions_panel.render_management`.
- Everything else (preset, colour pickers, sliders, session seeding of the point)
  stays as-is.

### `ui/ps_mode.py` — loses the post-editor OSL block

- Delete the OSL rendering block after `editor.render` (current lines ~89–133): the
  `st.divider()` + subheader, the `apply_osl` call, the bottom `st.image(...preview…)`,
  and `results.render_osl_steps(osl_result)`.
- **Keep** the project-seed logic (current lines ~96–116) that hydrates the OSL
  session keys from a loaded project's persisted params — but move it to run **before**
  `editor.render` (it only seeds `session_state`, so position is the only change).

**Move the OSL steps to the Paint tab (`app.py`).** Today the glow steps render
*inline in the Studio tab* via `ps_mode.py:133`, right below the editor — that call is
part of the deleted block. The region steps, by contrast, live in the **Paint tab**
(`app.py:86` → `results.render_steps(multi)`). The glow steps belong next to them:
add `results.render_osl_steps(st.session_state.get(keys.OSL_RESULT))` to `tab_paint`
after `render_steps(multi)`. `editor.render` now sets `keys.OSL_RESULT`, so the Paint
tab reads a fresh result each rerun. This also finally makes `render_osl_steps`'s
docstring ("call right after `render_steps()` in the Paint tab") true — today it is not.

### `ui/results.py` — enriched glow-step captions (#4)

Replace the bare `caption=(s.label or "glow zone")` in `render_osl_steps` with
layer-aware glazing guidance, keyed off the step's position in the nested sequence
(the glow bands are strictly nested broad → tight; see the OSL design's `osl_bands`):

- **first / broadest:** "Thin glaze of **{paint}** over every surface facing the light
  — keep it broad and faint, build it up in several watery passes."
- **middle layer(s):** "Tighten **{paint}** onto the surfaces closest and most
  face-on to the source; a little less thinned."
- **last / hotspot:** "Hotspot — near-pure **{paint}** on the single point nearest the
  source. Leave surfaces turned away dark."

`{paint}` is still `s.label` (the nearest named paint from `matching.match`); this only
wraps it in technique text, the way region steps already get technique-aware captions
via `helpers.render_region_steps`. A tiny pure function
`osl_step_caption(index, n_steps, paint_name) -> str` makes the wording unit-testable.

## What stays byte-identical

- `src/mini_highlight_advisor/osl.py` — glow math (`osl_field`, `osl_ramp`,
  `osl_bands`, `osl_colors`, `osl_field_multi`).
- `src/mini_highlight_advisor/pipeline.py: apply_osl` — signature and behaviour.
- Region plans, the swatch board, and every non-OSL step.
- The OSL persistence format in `projects.py` and the session keys in `ui/keys.py`.

## Data flow (per rerun, PS mode, glow enabled + placed)

```
ps_mode.render
  → seed OSL session keys from loaded project (if any)         [moved up]
  → editor.render(relit_rgb, mask_u8, book, shading, normals…)
      → pre-sync visibility toggles                            [existing]
      → multi = run_analysis(...)                              [existing]
      → build_osl_result(multi.combined_rgb, normals, mask,
                          osl params from session, owned, catalog)
            → apply_osl(...) → (preview_rgb, OslResult)
      → st.image(preview_rgb)          # glow now in MAIN preview
      → session[OSL_RESULT] = OslResult
      → tabs: Manage | Colour | Technique | Glow(PS only)
            Glow → osl_panel.render(mask.shape, multi.combined_rgb)
                     # click canvas shows the mini; writes params for next run
  → (Paint tab elsewhere) results.render_osl_steps(session[OSL_RESULT])
        # enriched glazing captions
```

## Testing

- **`ui/helpers.py` (or editor) `build_osl_result` unit** (Streamlit-free, synthetic
  hemisphere from `tests/fixtures/ps/generate_synth.py`):
  - glow disabled / no point → returned preview is byte-identical to `combined_rgb`
    and `OslResult` is `None`;
  - enabled + placed → preview differs only where glow > 0, brightens toward
    `hot_rgb` near the source, unchanged off-mask.
- **`osl_step_caption` unit:** 2-, 3-, and 4-step sequences each yield first=broad
  wording, last=hotspot wording, middles=tighten; the paint name is interpolated.
- **Click rescale:** a click at display-canvas `(dx, dy)` maps to full-res
  `(dx·src_w/disp_w, dy·src_h/disp_h)` (guards the new scaled-canvas back-conversion).
- **UI smoke:** the editor shows 4 tabs in PS mode and 3 in photo mode (Glow hidden
  without normals); toggling the glow off removes both the preview glow and the steps.

## Non-goals (unchanged from the OSL feature)

- No Path-L (no-normals) OSL — the Glow tab is PS-mode only.
- No multiple simultaneous sources in the UI (math supports it; UI ships one).
- No change to the glow model, ramp, or banding.
- No "Add glow steps" button — live apply, gated by the enable toggle.

## Build order (for the plan)

1. `osl_step_caption` + wire into `results.render_osl_steps` (self-contained, #4).
2. Fix the placement canvas: background image + display-scale + click rescale in
   `osl_panel.render` (#1) — with the rescale unit test.
3. `build_osl_result` helper wrapping `apply_osl` + its unit test.
4. `editor.render`: pre-preview composite, 4th Glow tab (PS-only), store `OSL_RESULT`
   (#2 + #3).
5. `ps_mode.render`: delete the post-editor OSL block, move the seed logic up, ensure
   the Paint tab renders `render_osl_steps` from `keys.OSL_RESULT`.
6. UI smoke test + `CLAUDE.md` note that OSL now lives in the editor's Glow tab.
```
