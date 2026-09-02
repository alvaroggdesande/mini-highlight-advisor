# Studio UX & Colour Loop — Design Spec

**Date:** 2026-09-02
**Branch:** feat/studio-ux-colour-loop
**Status:** Spec — pending implementation plan

## Problem

Two symptoms with the same root cause:

1. **The render is invisible during decision-making.** The mini image is drawn at the bottom of a long control stack (regions → palette editor → coverage → match-to-paints → edge toggles → technique → relief cap → photo quality → analyze → render). Users scroll past everything to see it, then scroll back up to change a setting.

2. **The colour flow is fragmented into five competing surfaces.** "What colours do I use?" is asked in five different places with different scopes and different UIs, none aware of each other:
   - `scheme_gen_panel` — whole-mini scheme (surfaces + mood + hero)
   - palette_editor "Generate from midtone" — one region's ramp
   - palette_editor "Colour variants" — one region's harmony alternatives
   - palette_editor slots — one band at a time
   - "Match to my paints" — consequence panel floating in results

   Three of these are the same conceptual action ("give me a ramp") offered at different scopes with different UIs. They compete instead of nesting. The preview thumbnail (`_mini_preview`) exists but is buried inside collapsed expanders.

3. **Phase mismatch.** Paint-along steps (dark → light per band) are execution-time output, but they sit alongside the decision-time controls. You want to see the mini + scheme while deciding; you want the steps when you're at the paint station.

## Design

### Tab structure

Replace the current three tabs (Miniature / Paints / All angles) with five:

| Tab | Purpose |
|-----|---------|
| 🖌️ **Studio** | Visualise and decide: upload, regions, colour, technique |
| 🪜 **Paint** | Execution: paint-along steps per region, dark → light |
| 🎨 **Paints** | Owned-paint inventory (unchanged) |
| 🖼️ **All angles** | Gallery of angles (unchanged) |
| 📷 **Capture & help** | Shooting guide, photo-quality explainer, tips |

**Loading order note (existing constraint):** `st.tabs` runs all tab bodies every rerun in code order. The Paints tab must still execute before Studio so that `owned_codes` / `owned_paints` are finalised before Studio renders ownership badges. Display order is controlled by the label list, not code order — keep this pattern.

### Studio tab layout

```
STUDIO
 project ▾    input: [Photo] [Normal map]
 angles: [1][2][+]

┌────────────────┬─────────────────────────┐
│                │ (Regions) Colour  Tech   │  ← sub-tabs
│   MINI RENDER  │ ─────────────────────── │
│   (live)       │  [content for active    │
│                │   sub-tab]              │
│                │                         │
└────────────────┴─────────────────────────┘
```

- Left column (~50% width): mini render, always visible, updates on every change.
- Right column (~50% width): three sub-tabs — **Regions**, **Colour**, **Technique**.
- The upload widget and "no photo yet" state sit above the two-column layout, full-width, and collapse once a photo is loaded.
- Steps are absent from Studio entirely — they live in the Paint tab.
- Photo-quality check (the compact status lines, not the guide) remains as a small inline note near the render. The verbose guide and expander move to Capture & help.

### Regions sub-tab

Current content of `ui/regions_panel.py` + coverage slider. No logic change in Stage 1; just relocated.

Longer-term (Stage 3 polish): the region selector and lasso tool sit here naturally.

### Colour sub-tab — the core redesign

Three nested levels, progressive disclosure. The mini render on the left updates live at every level. There is no separate preview thumbnail — **the mini is the preview**.

```
Colour
─────────────────────────────────────────
▼ Generate whole-mini scheme             ← collapsible, starts expanded on first use
  surface per region + hero + mood
  [✨ Generate & apply]

─────────────────────────────────────────
  This region: Cloak          ← region selector (mirrors Regions sub-tab selection)
  Base colour ████ #3a2060
  [Ramp from midtone]  [Complementary]  [Warm]  [Cool]
  (quick-apply buttons, no separate apply step)

─────────────────────────────────────────
  Bands (dark → light)
  [1] ████ Vallejo 70.861 · ✅ owned
  [2] ████ Custom #4a3070  · closest: 70.862 ⚠️ not owned  [↕ blend]
  [3] ████ ...
  [+ band]  [- band]   3–7

─────────────────────────────────────────
  Save scheme  [name ______] [＋ Save]
  Saved: [Grimdark ▾]  [Apply] [Delete]
─────────────────────────────────────────
```

**Level 1 — Whole-mini scheme (cold-start):**
- Surfaces + hero colour + mood + harmony variant, exactly as `scheme_gen_panel` does today.
- Collapsed by default once a scheme has been generated (session flag).
- On "Generate & apply": applies to all regions, reruns, mini updates.

**Level 2 — This region's ramp:**
- Merges "Generate from midtone" + "Colour variants" into one compact row of buttons.
- Each harmony button (Complementary / Warm / Cool) applies immediately — no extra "Apply" click.
- Apply is cheap and re-rollable: clicking another variant overwrites; "undo" is the previous named scheme (save before experimenting, or just re-apply Level 1 to reset).
- The `_mini_preview` thumbnail is dropped — the left-column render serves this role.

**Level 3 — Bands:**
- Current palette slots, one row per band, dark → light.
- Owned-first paint match shown inline per slot (absorbs the floating "Match to my paints" section).
- `blend neighbours` button stays for interior slots.
- Band count slider (3–7) stays.

**Scheme save/load** at the bottom of the Colour sub-tab, not as a separate panel. Replaces `schemes_panel`.

**Recipe save/load** (the current "Save as recipe" expander) collapses into a secondary action alongside the save scheme control. One save surface, not two.

### Technique sub-tab

Current content: technique picker (Smooth / Drybrush / NMM), edge highlight toggles, relief cap, recess shades. Relocated from `results.py` into its own sub-tab. No logic change in Stage 1.

### Paint tab

Contains the paint-along steps only:
- `st.subheader("Paint-along steps by region")`
- Per-region `helpers.render_region_steps(...)` exactly as today.
- The swatch board (`swatch_board`) can live here too.
- If no analysis has run yet (no photo), show a placeholder: "Set your colours in Studio first, then come here to paint."

The Paint tab reads from `st.session_state[keys.LAST_MULTI]` which is already populated by the Studio render — no re-analysis needed.

### Capture & help tab

Contains, verbatim:
- `SHOOTING_GUIDE` (the full shooting guide markdown)
- `PAINTED_CAPTURE_NOTE`
- The `with st.expander("How to photograph your mini")` content, now top-level
- The compact photo-quality check lines move here too (or stay in Studio — see decision below)

**Decision — photo quality location:** keep the compact status lines (the green ✅ / warning ⚠️ check rows) in Studio near the render, where they're actionable. Move only the verbose guide text to Capture & help. The `input_check.check_input` call stays in Studio.

### Capture & help tab — PS mode

PS mode (`tools/ps_tool.py` capture guide, `docs/ps-capture-guide.md`) lives here too. Currently it is referenced in the input mode radio help text; add a short "PS capture protocol" section here.

## What doesn't change

- All core logic: `pipeline.py`, `overlay.py`, `matching.py`, `scheme_gen.py`, `scheme_build.py`, `banding.py`, `regions.py`, `region_state.py`.
- The dual-path constraint (Path L / Path P), the `normal_field=` seam, PS mode entry point.
- The Paints tab and All angles tab.
- Session-state key names (no widget key churn).

## Staging plan (three independent PRs)

### Stage 1 — Skeleton reflow (zero logic change)

Goal: immediately fix "render too far down" and establish the new tab shell. Mechanical move only — no UI logic changes.

Changes:
- `app.py`: replace `tab_mini, tab_paints, tab_gallery` with `tab_studio, tab_paint, tab_paints, tab_angles, tab_capture`
- Inside `tab_studio`: split into `col_render, col_controls = st.columns([1, 1])`; render goes in `col_render`, existing editor call goes in `col_controls` (temporarily, before sub-tabs)
- Inside `tab_paint`: move the steps rendering block (currently at the bottom of `results.py`) here; read from `keys.LAST_MULTI`
- Inside `tab_capture`: move `SHOOTING_GUIDE` expander + `PAINTED_CAPTURE_NOTE` here; keep compact check lines in Studio
- `ui/results.py`: extract steps rendering into a standalone `render_steps(multi)` function that `tab_paint` calls

This PR is safe to review and merge before Stages 2 and 3 because it moves display code only, not logic.

### Stage 2 — Unified Colour flow

Goal: consolidate the five colour surfaces into the three-level Colour sub-tab.

Changes:
- New `ui/colour_panel.py`: three-level panel (whole-mini scheme → region ramp → bands). Absorbs logic from `scheme_gen_panel.py`, the midtone/variants expanders in `palette_editor.py`, the "Match to my paints" block in `results.py`, and `schemes_panel.py`.
- `ui/palette_editor.py`: strip to bands-only (Level 3 of `colour_panel`), then inline into `colour_panel.py`. The module is deleted once absorbed — no orphan file.
- `ui/scheme_gen_panel.py` and `ui/schemes_panel.py`: deleted once absorbed.
- `ui/results.py`: remove "Match to my paints" block; remove midtone/variants expanders (now in colour_panel).
- `app.py` Studio sub-tabs wired up: `tab_regions, tab_colour, tab_technique = st.tabs(["Regions", "Colour", "Technique"])`.
- Session state: add one flag `keys.SCHEME_GENERATED` (bool) to track whether Level 1 should start collapsed.

### Stage 3 — Regions & Technique sub-tabs + polish

Goal: complete the sub-tab split for Regions and Technique; Capture tab polish.

Changes:
- `ui/regions_panel.py` into the Regions sub-tab (already extracted; just routing).
- `ui/coverage_editor.py` alongside regions (coverage is a region property).
- Technique picker + edge toggles + relief cap → Technique sub-tab from `results.py`.
- `ui/capture_panel.py`: PS capture guide section added.
- Any remaining `st.divider()` / stray content from `results.py` cleaned up.

## Open questions (resolved)

**Preview-before-apply for harmony variants:** Removed. With the mini render live on the left, apply is the preview. Revert by re-applying Level 1 scheme or clicking another variant. This removes the `_mini_preview` thumbnail from palette_editor.

**Scheme save vs recipe save:** Merged into one "Save as scheme" control. Recipes (the JSON files) remain as the storage mechanism; the "Save as recipe" label is renamed to "Save scheme".

## Files touched (summary)

| File | Stage | Action |
|------|-------|--------|
| `app.py` | 1 | New tab structure, two-column layout |
| `ui/results.py` | 1 + 2 | Extract `render_steps()`; remove colour blocks |
| `ui/colour_panel.py` | 2 | New file — the three-level colour panel |
| `ui/scheme_gen_panel.py` | 2 | Deleted (absorbed) |
| `ui/schemes_panel.py` | 2 | Deleted (absorbed) |
| `ui/palette_editor.py` | 2 | Strip to bands-only (Level 3) |
| `ui/regions_panel.py` | 3 | Routed to Regions sub-tab |
| `ui/coverage_editor.py` | 3 | Routed to Regions sub-tab |
| `ui/capture_panel.py` | 3 | New file — Capture & help content |
