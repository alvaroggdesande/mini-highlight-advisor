# OSL — Object-Source Lighting (PS point-source, add-on glow layer)

**Date:** 2026-09-04
**Status:** Approved design — ready for implementation plan.
**Branch:** `feat/osl-object-source-lighting`

## What this is

Object-Source Lighting (OSL): painting the effect of a light that is *part of the
model* — a lantern, a glowing blade, a plasma coil, a gem. The tool places a
**coloured point light at a spot the user clicks**, computes how much that glow
reaches every point on the mini using the recovered PS normals, and emits **extra
paint-along steps** for glazing the glow on top of the existing region plans.

This is the **PS virtual-light** version (uses normals), not the cheap Path-L
directional slice. It reuses machinery that already exists: `relight.py`'s N·L
light-field idea, `banding.py`, `overlay.py`'s `per_band_images`, `matching.py`
for paint naming, and the `st_canvas` click capture already used for region lassos.

## Decisions locked in brainstorming (2026-09-04)

1. **PS virtual-light**, not the cheap Path-L slice. Requires the normal map.
2. **Point source** at a clicked spot (true OSL), not a distant directional light.
3. **Screen-space distance falloff + real N·L** for facing. No depth/height map is
   available from PS (SDM-UniPS emits only `normal.png` / `baseColor.png` /
   `mask.png`), so "how far" is measured in image space and tuned by a slider. This
   is honest: the absolute depth scale is unknowable regardless.
4. **Add-on glow layer.** Each region's normal highlight plan is left byte-identical;
   OSL appends glow steps after it, the way a painter paints the object then adds the
   light effect on top.
5. **Hotspot = hue-tinted white** (green-white, orange-white…), not pure white.
6. **Single source in v1.** The field is built to composite N sources (`max` over
   per-source fields) so a second glow is "add another to the list, same math."

## Non-goals (v1)

- No Path-L (no-normals) OSL — panel is hidden without normals. (Later phase.)
- No multiple simultaneous sources in the UI (math supports it; UI ships one).
- No true 3D depth / normal integration. Screen-space approximation only.
- No specular beyond the white-hot push. Diffuse glow only (mirrors `relight.py` v1).

## The model (`osl.py`, pure numpy, torch-free)

Given `normals` (H,W,3) in the pinned convention (R=x-right, G=y-up, B=z-toward
viewer), a boolean `mask`, and user params, the per-pixel glow amount is:

```
source  = [click_x, click_y, height]           # height ≥ 0: how far the light floats off the surface plane
xy      = pixel grid coords (x right, y down-image)
L(p)    = normalize(source - [x, y, 0])         # per-pixel direction TO the source
facing  = clip(dot(normals, L(p)), 0, 1)        # real normals: surfaces turned toward the glow light up
dist    = ||source_xy - p_xy||                  # screen-space distance from the click
falloff = 1 / (1 + (dist / reach)^2)            # reach slider; ≈1 at source, →0 far away
glow(p) = clip(intensity * facing * falloff, 0, 1)
glow[~mask] = 0
```

**Convention note (load-bearing):** the normal map's Y (green) is *up* in the pinned
convention, while image row index increases *downward*. When building `L(p)` the
implementation must convert the click/pixel grid into the same axis convention the
normals use (flip the image-y sign for the dot product, or equivalently negate the
G comparison). This is exactly the class of bug that produced the NMM stripe issue —
the plan's first test must pin the axis so "a face pointing at the click lights up"
holds. Reuse `tests/fixtures/ps/generate_synth.py` for a known hemisphere.

The critical property that makes this read as a *light source* and not a coloured
stain: `facing` uses the real normals, so a surface **near** the source but **turned
away** from it stays dark.

### Colour ramp

`glow(p)` drives a three-stop ramp blended over the current painted preview:

```
0            → base colour shows through (no glow)
mid          → glow_rgb glazed in
high (→1)    → hot_rgb, where hot_rgb defaults to a hue-tinted white
               (e.g. mix(glow_rgb, white, ~0.7) — carries the glow's hue, not pure white)
```

`osl_ramp(glow, glow_rgb, hot_rgb) -> (H,W,3)` returns the glow contribution;
`overlay.osl_preview` screens/adds it over the base preview. `hot_rgb` is a UI
control defaulting to the hue-tinted white.

### Banding the glow into steps

`osl_bands(glow, mask, n_layers) -> bands` slices `glow` into **2–4 nested layers**
using `banding.py` (each brighter layer is a strict subset of the previous):

- **Glow 1 (broad, faint):** glaze `glow_rgb` everywhere `glow > t₁`.
- **Glow 2 (tighter):** stronger `glow_rgb` where `glow > t₂`.
- **Glow 3 (hotspot):** `hot_rgb` pop, tightest zone nearest the source.

Each glow layer becomes a `BandStep` via the existing `per_band_images` path, with
its paint **named from the active palette/catalogue** through `matching.py` (nearest
paint to `glow_rgb`, to the mid mix, and to `hot_rgb`). Captions follow the
future-doc rule: name a real paint, say where it goes, brightest near the source.

### N-source shape (built now, single call in v1)

`osl_field` takes one source. A thin composer `osl_field_multi(sources) = max over
osl_field(s)` is the v1-unused seam; the UI passes a single source. Documented so
phase 2 is additive.

## Architecture / where code lives

- **`src/mini_highlight_advisor/osl.py`** (new) — `osl_field`, `osl_ramp`,
  `osl_bands`, `osl_field_multi`. Pure numpy, torch-free, Streamlit-free. Sits next
  to `relight.py`. The reserved `osl_light()` comment in `materials.py` gets a
  one-line pointer here (OSL is bigger than a shader; `materials.py` stays NMM-focused).
- **`overlay.py`** — add `osl_preview(base_preview, glow_rgb_field)` and reuse
  `per_band_images` for the glow step images.
- **`pipeline.py`** — `apply_osl(result, normals, mask, params) -> result` runs as a
  **post-process** after `analyze_regions`. It appends glow `BandStep`s to the
  result and leaves every region's base plan byte-identical. OSL never touches the
  core banding path.
- **`matching.py`** — reused as-is to name glow paints.

## UI (`ui/osl_panel.py`, PS-mode only)

Sibling to `ui/relight_panel.py`, rendered only when normals exist:

- **Click-to-place** the source via the existing `st_canvas` (+ `ui/geometry.py`
  vertex extraction); a single click/point. No new dependency.
- **Glow colour** picker and **hotspot tint** (defaults to hue-tinted white).
- **Height / Reach / Intensity** sliders + presets ("Torch", "Plasma", "Gem").
- **Live glow preview** (composited image) that updates on slider/click change so
  the user tunes where the light lands before committing.
- **"Add glow steps"** button → runs `apply_osl`; glow steps appear in the
  plan/gallery and persist with the project (via `projects.py`).
- Path-L (no normals): panel hidden with a one-line "OSL needs the PS normal path".

Streamlit reruns on every interaction (same as `relight_panel`); the caller
re-derives the glow preview from (source, colour, sliders). No real-time mouse drag
is required — click + rerun is the interaction.

## Testing

- **`tests/test_osl.py`** on a synthetic hemisphere (`tests/fixtures/ps/generate_synth.py`):
  - glow peaks at/near the click point;
  - a face turned **away** from the source stays dark even when close (proves N·L
    modulation, the anti-stain property);
  - falloff strictly monotonic decreasing in screen distance;
  - `glow[~mask] == 0`;
  - **axis pin**: a normal pointing straight at the click lights up (guards the
    image-y / green-up convention);
  - ramp endpoints: `glow==0` → base, `glow==1` → `hot_rgb`;
  - glow bands strictly nested (each brighter band ⊂ the previous).
- **Pipeline test**: `apply_osl` appends exactly `n_layers` steps and leaves base
  region steps unchanged (byte-identical).
- **UI smoke**: panel renders only in PS mode; hidden without normals.

## Constraints recap (v1)

PS-only · single source · diffuse glow (white-hot push is the only "specular") ·
screen-space depth approximation stated in the UI · never build on `main` (feature
branch + PR).

## Build order (for the plan)

1. `osl.py` core: `osl_field` (+ axis pin test) → `osl_ramp` → `osl_bands`.
2. `overlay.osl_preview` + glow `per_band_images`.
3. `pipeline.apply_osl` post-process + pipeline test.
4. `ui/osl_panel.py` + wire into PS mode + persistence + UI smoke test.
5. Docs: `CLAUDE.md` module-map line; short usage note in the PS/relight area.
