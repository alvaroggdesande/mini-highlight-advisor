# v1.2 — Step-image readability polish (+ project docs)

**Date:** 2026-08-09
**Status:** Approved (design)
**Branch:** `feat/step-image-readability`

## Goal

Make the v1.1 per-band step images actually legible, and give the project
onboarding docs. Two readability problems surfaced from a real run (user
screenshot of a primed Necron on a scenic base):

1. **The white outline ring is speckle noise.** Bands fragment into thousands
   of tiny islands, so the per-pixel contour becomes noise across detailed areas
   rather than a clean boundary.
2. **Dark paints are invisible.** Dark layers (e.g. Abaddon Black + Leadbelcher,
   both near-navy) painted at alpha over a background dimmed to 25% are
   dark-on-dark — the painter cannot see the zone.

Plus: rewrite `README.md` and add a `CLAUDE.md` so future work ramps quickly.

## Background (current state, post-v1.1 merge)

- `overlay.py` has `BandStep(index, cumulative_rgb, exact_rgb, is_last)` and
  `per_band_images(rgb, bands, mask, colors, alpha=0.78)`.
- `_render_step(rgb, active_mask, color, alpha)` builds each step image:
  non-active pixels dimmed by `_DIM = 0.25`, active region painted with the paint
  color at `alpha`, then a white outline ring (`_outline_ring`, dilate-XOR) drawn
  around the active region.
- `paint_preview` (the combined preview panel) also uses `_DIM = 0.25` and is
  **out of scope** here — leave it untouched.
- `pipeline.analyze` attaches `steps` to `HighlightResult`; `app.py` shows a
  "Paint-along steps" section, 2 images per step (1 for the last).
- Input scope: primed / zenithal-primed (monochrome) minis; whole mini treated
  as one region. Conventions: `bands` int array, off-mask `-1`,
  `mask == (bands >= 0)`, band 0 darkest → n-1 lightest; luminance-based lighting.

## Design

### Three images per step

Each `BandStep` carries three renders (two on the last step):

- **Zone marker** (`zone_rgb`) — the **cumulative** region (`bands >= k`) filled
  with a **fixed bright accent** so it is visible regardless of the paint color.
  This is the primary "where do I paint this step" view. Present on every step.
- **Apply across** (`cumulative_rgb`) — cumulative region in the **paint color**.
- **Ends up here** (`exact_rgb`) — exact region (`bands == k`) in the paint color;
  `None` on the last step (cumulative == exact there).

The last step therefore shows 2 images (zone + one color); every other step
shows 3.

### Shared background: desaturate + dim

All three images render the non-active area as **greyscale × `_STEP_DIM`**
(new constant `_STEP_DIM = 0.4`). A neutral mid-grey surround gives any paint
color — dark navy included — something to contrast against, while the mini's
shape stays faintly visible for context. Greyscale reuses standard luminance
weights (`0.299 R + 0.587 G + 0.114 B`). The combined-preview `_DIM = 0.25` is a
separate constant and stays as-is.

### Accent color

Module constant `_ACCENT = np.array([255, 40, 200], np.float32)` (magenta).
Chosen because minis and previews skew grey / blue / metal / brown, so magenta
never collides with a paint color. Retunable in one place.

### Outline dropped

Remove the outline ring from the step images. The zone marker now carries "where",
so the speckle source is gone. `_outline_ring` and `_OUTLINE` become dead code and
are deleted (they are not used anywhere else).

### Code shape (`overlay.py`)

```python
_STEP_DIM = 0.4
_ACCENT = np.array([255, 40, 200], np.float32)
_LUMA = np.array([0.299, 0.587, 0.114], np.float32)


@dataclass
class BandStep:
    index: int
    zone_rgb: np.ndarray          # cumulative region as bright accent marker
    cumulative_rgb: np.ndarray    # cumulative region in paint color
    exact_rgb: np.ndarray | None  # exact region in paint color; None if is_last
    is_last: bool


def _desat_dim(rgb) -> np.ndarray:
    # full-frame greyscale * _STEP_DIM background base, float32 (H,W,3)
    lum = rgb.astype(np.float32) @ _LUMA
    return (np.stack([lum, lum, lum], axis=-1)) * _STEP_DIM


def _render_step(rgb, active_mask, color, alpha) -> np.ndarray:
    base = rgb.astype(np.float32)
    out = _desat_dim(rgb)
    out[active_mask] = (1 - alpha) * base[active_mask] + alpha * color
    return np.clip(out, 0, 255).astype(np.uint8)


def _zone_render(rgb, active_mask, accent=_ACCENT, alpha: float = 0.85) -> np.ndarray:
    base = rgb.astype(np.float32)
    out = _desat_dim(rgb)
    out[active_mask] = (1 - alpha) * base[active_mask] + alpha * accent
    return np.clip(out, 0, 255).astype(np.uint8)
```

`per_band_images` computes, per step: `zone = _zone_render(rgb, (bands>=k)&mask)`,
`cumulative = _render_step(rgb, (bands>=k)&mask, color, alpha)`,
`exact = None if is_last else _render_step(rgb, (bands==k)&mask, color, alpha)`,
and constructs `BandStep(index=k, zone_rgb=zone, cumulative_rgb=cumulative,
exact_rgb=exact, is_last=is_last)`.

`pipeline.analyze` needs no change (calls `per_band_images` with defaults).

### App (`app.py`)

In the "Paint-along steps" loop, per step:

```python
if step.is_last:
    c1, c2 = st.columns(2)
    c1.image(step.zone_rgb, caption="Where to paint", use_container_width=True)
    c2.image(step.cumulative_rgb, caption="Apply across", use_container_width=True)
else:
    c1, c2, c3 = st.columns(3)
    c1.image(step.zone_rgb, caption="Where to paint", use_container_width=True)
    c2.image(step.cumulative_rgb, caption="Apply across", use_container_width=True)
    c3.image(step.exact_rgb, caption="Ends up here", use_container_width=True)
```

The section caption is updated to explain the three views.

### Docs

- **README.md** (rewrite): one-paragraph pitch (photo of a primed mini →
  where/what/how-far to highlight); the primed-only / whole-mini-as-one-region
  scope and why (luminance approach); install (`.venv`, `pip install -r`),
  run (`streamlit run app.py`); pipeline at a glance
  (upload → mask → luminance light → curved banding → palette → overlay + steps);
  a "Paint-along steps" description; roadmap (per-material LLM regions, SAM masks,
  colored-mini support, PDF export); link to `docs/superpowers/specs/`.
- **CLAUDE.md** (new): module map of `src/mini_highlight_advisor/`
  (palette / banding / lighting / masking / overlay / pipeline — one line each);
  the core conventions (`bands` partition with `-1` off-mask, `mask == bands>=0`,
  band 0 darkest, luminance = the shading map for primed minis); the two hard
  constraints (primed-only, whole-mini-as-one-region) and where v2 lifts them;
  how to run tests (`.venv/Scripts/python -m pytest`) and the app; the
  spec → plan → subagent-driven workflow and where docs live.

## Testing

Update `tests/test_overlay.py` (the v1.1 tests that assumed the old dim/outline)
and add coverage:

1. **Background is greyscale + dimmed.** With a *colored* uniform input (e.g.
   RGB `(100, 40, 20)`), every non-active pixel in a step image satisfies
   `R == G == B` (desaturated) and equals `round(luma * 0.4)`.
2. **`zone_rgb` present on every step**, shape/dtype match input.
3. **Zone accent region == `(bands >= k) & mask`.** Using a uniform-grey input so
   the background is grey (`R==G==B`) and accent-painted pixels are non-grey,
   assert the non-grey region equals `(bands >= k) & mask`.
4. **Color-fill active region == paint color** at `alpha=1.0` — cumulative equals
   `(bands>=k)&mask`, exact equals `(bands==k)&mask` (as v1.1, still holds).
5. **Cumulative regions nested/shrinking** (unchanged invariant).
6. **Last step**: `exact_rgb is None`, `is_last True`; others have `exact_rgb`.
7. **No outline artifacts**: no non-active pixel is pure white `(255,255,255)`
   for a non-white input (guards the outline removal).

Update `test_nonactive_interior_pixel_is_dimmed`: uniform `100` input →
greyscale `100` → `× 0.4` → `[40, 40, 40]` (was `[25,25,25]`).

Docs have no automated test. `app.py` change verified by user browser smoke test.

## Scope guard (deferred / untouched)

- No toggle parameters (accent color, dim factor, on/off) — constants only.
- `paint_preview` / combined preview panel untouched.
- No changes to banding / masking / lighting / palette.
- No PDF export, no download buttons, no per-material regions, no colored-mini
  work — those are separate roadmap items.

## Files touched

- `src/mini_highlight_advisor/overlay.py` — new constants + `_desat_dim` +
  `_zone_render`; rework `_render_step`; delete `_outline_ring`/`_OUTLINE`;
  extend `BandStep` + `per_band_images`.
- `app.py` — 3-column step layout + updated caption.
- `tests/test_overlay.py` — updated + new tests.
- `README.md` — rewrite.
- `CLAUDE.md` — new.
