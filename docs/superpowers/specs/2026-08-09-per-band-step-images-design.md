# v1.1 — Per-band step-by-step images

**Date:** 2026-08-09
**Status:** Approved (design)
**Branch:** `feat/per-band-step-images`

## Goal

Give the painter a layer-by-layer walkthrough. For a mini banded into `n`
highlight layers (dark → light), produce a sequence of step images. Each step
isolates the area to paint with one paint so the user can follow along
physically, one paint at a time, instead of interpreting the single combined
preview.

This is a thin additive slice on top of the shipped v1 pipeline. It introduces
no new models, dependencies, or tuning parameters — it re-renders the existing
`bands` partition.

## Background (what already exists)

- `banding.band_light` produces `bands`: an `int` array where every masked pixel
  is assigned to exactly one band, `0` = darkest (Shadow) … `n-1` = lightest
  (Edge Highlight). It is a **partition** (each pixel in one band).
- `overlay.paint_preview(rgb, bands, mask, colors, alpha=0.78)` renders the
  combined preview: non-masked pixels dimmed to 25%, each band painted with its
  paint color at `alpha`.
- `pipeline.analyze` returns a `HighlightResult` carrying `mask`, `bands`,
  `coverage`, `roles`, `preview_rgb`, `panel`.
- `app.py` shows the panel plus a text layer guide.

## Design

### What each step shows

For step `k` (0 = darkest, painted first):

- The **active region** is painted with paint `k`'s actual color at the existing
  preview alpha (`0.78`) — the painter sees *where*, *what color*, and *how much*.
- Everything else (rest of the mini + off-model background) is **dimmed to 25%**,
  reusing `paint_preview`'s existing dim factor.
- A **thin bright contour** is drawn around the active region for a crisp
  boundary, computed by a cheap morphological edge (dilate the active mask, XOR
  with itself) — no `cv2.findContours`, which is fragile on many tiny highlight
  islands, and no new dependency.

### Two images per step (the pair)

Each step renders up to two images that together make the layering explicit:

- **Cumulative** — active region = `bands >= k`. Reads as *"apply paint k across
  all of this."*
- **Just-this-band** — active region = `bands == k`. Reads as *"…and this slice
  is what stays paint k after you highlight over it."*

Consequences that fall out for free:

- Step 0 cumulative = the entire model (the dark base-coat); step 0 just-band =
  only the deepest recesses. The "recesses first" story is told with no synthetic
  extra step.
- For the **last** band, `bands >= k` and `bands == k` are identical. That step
  therefore renders a **single** image (no confusing duplicate).

### New code — `overlay.py`

```python
@dataclass
class BandStep:
    index: int                 # 0-based band index
    cumulative_rgb: np.ndarray # active region = bands >= index
    exact_rgb: np.ndarray | None  # active region = bands == index; None if is_last
    is_last: bool

def per_band_images(rgb, bands, mask, colors, alpha: float = 0.78) -> list[BandStep]:
    ...
```

- Pure numpy/PIL. Reuses `paint_preview`'s dim-and-color logic (factor `0.25`,
  alpha `0.78`) rather than duplicating constants — a small private helper renders
  "paint `active_mask` with `color`, dim the rest, outline the active region".
- Returns exactly `len(colors)` steps in dark→light order.

### Pipeline wiring — `pipeline.py`

- `HighlightResult` gains `steps: list[BandStep]`.
- `analyze` computes it from the `bands`/`mask`/`colors` it already has:
  `steps = per_band_images(rgb, bands, mask, colors)`.

### App wiring — `app.py`

- After the existing panel + layer guide, add a **"Paint-along steps"** section.
- Render steps in order. Each step:
  - Subheader: `Step {k+1} — {role} · {paint name}  (~{cov}% of the model)`
    (labels from the existing `roles` / `palette` / `coverage`).
  - Two Streamlit columns: **Apply across** (cumulative) | **Ends up here**
    (just-this-band).
  - For the last step: a single image (`Apply across` only), since the two coincide.
- Labels are Streamlit-side only; nothing is baked into the image (keeps images
  clean and reusable; a future PDF export can re-render captions).

## Testing (TDD)

Additions to `tests/test_overlay.py`, using a small synthetic `bands`/`mask`:

1. `per_band_images` returns exactly `n` steps, indices `0..n-1` in order.
2. Step 0's cumulative active region equals the full masked region.
3. Each step's `exact_rgb` active region equals `bands == k`.
4. Cumulative active regions are **monotonically nested / shrinking** as `k`
   increases (`region(k+1) ⊆ region(k)`).
5. Last step has `exact_rgb is None` and `is_last is True`; all others
   `is_last is False`.
6. Non-active pixels are strictly darker than the original `rgb` (dim applied).
7. Output image shapes/dtype match the input `rgb`.

## Scope guard (deferred — NOT in v1.1)

- **Future extension:** a parameter to toggle the active-region rendering between
  *paint-color fill* (v1.1 behavior) and *brightened real photo*. Noted for later;
  v1.1 ships the paint-color fill only.
- No PDF export, no download buttons.
- No per-step written prose beyond the label line.
- No recess sub-thresholding / synthetic wash step.

## Files touched

- `src/mini_highlight_advisor/overlay.py` — new `BandStep` + `per_band_images`.
- `src/mini_highlight_advisor/pipeline.py` — add `steps` to `HighlightResult`.
- `app.py` — "Paint-along steps" section.
- `tests/test_overlay.py` — new tests.
