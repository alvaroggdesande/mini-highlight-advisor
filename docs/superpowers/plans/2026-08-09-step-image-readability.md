# Step-image Readability Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the per-band step images legible (zone marker in a fixed accent + greyscale-dimmed background, outline removed) and add project onboarding docs (README rewrite + new CLAUDE.md).

**Architecture:** Rework the rendering in `overlay.py`: a shared `_desat_dim` background (greyscale × 0.4), a new `_zone_render` that fills the cumulative region with a fixed magenta accent, and a reworked `_render_step` that drops the outline. `BandStep` gains a `zone_rgb` field; `app.py` shows 3 images per step. Docs are refreshed to match the shipped tool.

**Tech Stack:** Python 3.11, numpy, opencv (`cv2`), Pillow, Streamlit, pytest.

## Global Constraints

- Package under `src/mini_highlight_advisor/`; tests under `tests/`; `app.py`, `README.md`, `CLAUDE.md` at repo root.
- `bands` is an int array; off-mask pixels are `-1`; `mask == (bands >= 0)`; band 0 = darkest, n-1 = lightest; partition.
- New constants (exact values): `_STEP_DIM = 0.4`; `_ACCENT = np.array([255, 40, 200], np.float32)` (magenta); `_LUMA = np.array([0.299, 0.587, 0.114], np.float32)`.
- Leave the combined-preview `paint_preview` and its `_DIM = 0.25` untouched.
- Zone marker uses accent at alpha `0.85`; color-fill uses paint color at alpha `0.78` (the existing default).
- No new pip dependencies.
- Run tests with `.venv/Scripts/python.exe -m pytest` (Windows).

---

### Task 1: Rework overlay rendering (zone marker + desaturated background, drop outline)

**Files:**
- Modify: `src/mini_highlight_advisor/overlay.py`
- Test: `tests/test_overlay.py`

**Interfaces:**
- Consumes: `rgb: np.ndarray uint8 (H,W,3)`, `bands: np.ndarray int`, `mask: np.ndarray bool`, `colors: list[np.ndarray float32 (3,)]`.
- Produces:
  - `BandStep` dataclass, field order: `index:int`, `zone_rgb:np.ndarray`, `cumulative_rgb:np.ndarray`, `exact_rgb:np.ndarray|None`, `is_last:bool`.
  - `per_band_images(rgb, bands, mask, colors, alpha: float = 0.78) -> list[BandStep]` — for step `k`: `zone_rgb` = cumulative region `(bands>=k)&mask` filled with `_ACCENT` at alpha 0.85 over a greyscale×0.4 background; `cumulative_rgb` = same region in paint color at `alpha`; `exact_rgb` = `(bands==k)&mask` in paint color (`None` if last); background of all images is greyscale (`R==G==B`) × `_STEP_DIM`. No outline pixels.
  - `_desat_dim(rgb) -> np.ndarray float32 (H,W,3)`; `_render_step(rgb, active_mask, color, alpha) -> np.ndarray uint8`; `_zone_render(rgb, active_mask, accent=_ACCENT, alpha=0.85) -> np.ndarray uint8`.
- Removed: `_outline_ring`, `_OUTLINE` (deleted — not used elsewhere).

- [ ] **Step 1: Update existing tests and add new ones in `tests/test_overlay.py`**

First, update the ONE existing assertion that depended on the old dim/outline. Find `test_nonactive_interior_pixel_is_dimmed` and change its final assertion from the old `[25,25,25]`/`sum` check to the new greyscale×0.4 value. Replace the whole test body with:

```python
def test_nonactive_interior_pixel_is_dimmed():
    rgb, bands, mask, colors = _fixture()  # uniform 100 input
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    # (0,0) is band 0: non-active in the last step (band 2), never painted.
    # Background = greyscale(100) * 0.4 = 40 per channel.
    out = steps[2].cumulative_rgb
    assert tuple(out[0, 0]) == (40, 40, 40)
```

Then append these new tests (the `_fixture` and `_painted_region` helpers already exist in the file from v1.1):

```python
def _non_grey(img):
    return (img[..., 0] != img[..., 1]) | (img[..., 1] != img[..., 2])


def test_every_step_has_zone_rgb_with_matching_shape():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors)
    assert all(s.zone_rgb is not None for s in steps)
    assert all(s.zone_rgb.shape == rgb.shape for s in steps)
    assert all(s.zone_rgb.dtype == np.uint8 for s in steps)


def test_zone_accent_region_equals_cumulative_region():
    # uniform-grey input => background stays grey (R==G==B); accent-painted
    # pixels become non-grey, so the non-grey region marks the active zone.
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors)
    for k, s in enumerate(steps):
        assert np.array_equal(_non_grey(s.zone_rgb), (bands >= k) & mask)


def test_step_background_is_greyscale_and_dimmed():
    # colored uniform input; luma = 0.299*100 + 0.587*40 + 0.114*20 = 55.66
    # background = int(55.66 * 0.4) = 22 per channel.
    bands = np.array(
        [[0, 0, 1, 2],
         [0, 0, 1, 2],
         [-1, -1, -1, -1],
         [0, 1, 1, 2]],
        dtype=np.int32,
    )
    mask = bands >= 0
    rgb = np.empty((4, 4, 3), np.uint8)
    rgb[:] = (100, 40, 20)
    colors = [np.array([255, 0, 0], np.float32),
              np.array([0, 255, 0], np.float32),
              np.array([0, 0, 255], np.float32)]
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    # row 2 is off-mask => non-active in every step => greyscale-dimmed
    bg_pixel = steps[0].cumulative_rgb[2, 0]
    assert bg_pixel[0] == bg_pixel[1] == bg_pixel[2]  # desaturated
    assert tuple(bg_pixel) == (22, 22, 22)            # exact dim value


def test_no_pure_white_outline_pixels():
    # guards outline removal: with a non-white input and non-white paints,
    # no pixel in any step image should be pure white.
    bands = np.array(
        [[0, 0, 1, 2],
         [0, 0, 1, 2],
         [-1, -1, -1, -1],
         [0, 1, 1, 2]],
        dtype=np.int32,
    )
    mask = bands >= 0
    rgb = np.empty((4, 4, 3), np.uint8)
    rgb[:] = (100, 40, 20)
    colors = [np.array([255, 0, 0], np.float32),
              np.array([0, 255, 0], np.float32),
              np.array([0, 0, 255], np.float32)]
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    for s in steps:
        for img in (s.zone_rgb, s.cumulative_rgb, s.exact_rgb):
            if img is not None:
                assert not np.any(np.all(img == 255, axis=-1))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_overlay.py -v`
Expected: FAILs — `test_every_step_has_zone_rgb_*` / `test_zone_accent_region_*` error with `AttributeError: 'BandStep' object has no attribute 'zone_rgb'`; `test_step_background_*` and `test_nonactive_interior_pixel_is_dimmed` fail on the old dim value; `test_no_pure_white_outline_pixels` may fail on the current outline.

- [ ] **Step 3: Rework `src/mini_highlight_advisor/overlay.py`**

Replace the constants block (currently lines ~18-19):

```python
_DIM = 0.25
_STEP_DIM = 0.4
_ACCENT = np.array([255, 40, 200], np.float32)
_LUMA = np.array([0.299, 0.587, 0.114], np.float32)
```

(Delete the `_OUTLINE = ...` line.)

Replace the `BandStep` dataclass:

```python
@dataclass
class BandStep:
    index: int
    zone_rgb: np.ndarray
    cumulative_rgb: np.ndarray
    exact_rgb: np.ndarray | None
    is_last: bool
```

Delete the `_outline_ring` function entirely.

Replace `_render_step` and add the two new helpers (keep `_render_step` above `per_band_images`):

```python
def _desat_dim(rgb) -> np.ndarray:
    lum = rgb.astype(np.float32) @ _LUMA
    grey = np.stack([lum, lum, lum], axis=-1)
    return grey * _STEP_DIM


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

Replace the `per_band_images` loop body so it also builds the zone image:

```python
def per_band_images(rgb, bands, mask, colors, alpha: float = 0.78) -> list[BandStep]:
    n = len(colors)
    steps: list[BandStep] = []
    for k, color in enumerate(colors):
        is_last = k == n - 1
        active = (bands >= k) & mask
        zone = _zone_render(rgb, active)
        cumulative = _render_step(rgb, active, color, alpha)
        exact = None if is_last else _render_step(rgb, (bands == k) & mask, color, alpha)
        steps.append(BandStep(index=k, zone_rgb=zone, cumulative_rgb=cumulative,
                              exact_rgb=exact, is_last=is_last))
    return steps
```

Note: `paint_preview` still uses `_DIM` — leave it exactly as-is.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_overlay.py -v`
Expected: PASS (all pre-existing overlay/per_band tests plus the 4 new tests). The `paint_preview` test (`test_paint_preview_colors_bands_and_darkens_background`) still passes because `paint_preview` is unchanged.

- [ ] **Step 5: Run the full suite (nothing else should break)**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS. `tests/test_pipeline.py` still passes — `analyze` calls `per_band_images` with defaults and does not touch `BandStep` fields by position.

- [ ] **Step 6: Commit**

```bash
git add src/mini_highlight_advisor/overlay.py tests/test_overlay.py
git commit -m "feat: zone-marker step images + desaturated background, drop outline"
```

---

### Task 2: 3-column step layout in the app

**Files:**
- Modify: `app.py:44-54` (the "Paint-along steps" section)

**Interfaces:**
- Consumes: `result.steps` (each `BandStep` now has `zone_rgb`, `cumulative_rgb`, `exact_rgb`, `is_last`, `index`), `result.roles`, `result.coverage`, sidebar `palette`.

No automated test (Streamlit UI). Verified by `ast.parse` (syntax) + user browser smoke test.

- [ ] **Step 1: Update the "Paint-along steps" block in `app.py`**

Replace the current caption + loop (lines 44-54) with:

```python
        st.subheader("Paint-along steps")
        st.caption("Work dark to light. 'Where to paint' = the zone for this paint "
                   "(bright marker); 'Apply across' = that zone in the paint colour; "
                   "'Ends up here' = the slice that stays this colour after you highlight over it.")
        for step, role, paint, cov in zip(result.steps, result.roles, palette, result.coverage):
            st.markdown(f"**Step {step.index + 1} — {role} · {paint.name}**  ·  ~{cov:.0f}% of the model")
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

- [ ] **Step 2: Verify the file parses**

Run: `.venv/Scripts/python.exe -c "import ast; ast.parse(open('app.py').read()); print('app.py parses OK')"`
Expected: prints `app.py parses OK`. Do NOT launch streamlit (user runs the browser smoke test).

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: 3-column paint-along step layout (zone + two colour views)"
```

---

### Task 3: Refresh project docs (README + CLAUDE.md)

**Files:**
- Modify: `README.md` (full rewrite — current content is a stale "nothing built yet" spike note)
- Create: `CLAUDE.md`

No automated test — prose docs. Verify by reading them back.

- [ ] **Step 1: Rewrite `README.md`**

Overwrite the file with:

```markdown
# Mini Highlight Advisor

Upload a photo of a **primed miniature** and get a paint-by-layer highlight plan:
where to highlight, which of your palette colours per layer, roughly how far each
band goes — as a painted preview on your own photo, a written layer guide, and a
**paint-along step sequence** (one set of images per layer, dark to light).

No existing tool does geometry-driven highlight overlays on your own photo:
text-only guides (PaintGuide.ai), hallucinated renders (AI-MiniPainter), and
finished-job scorers (MyMiniScore) all solve a different problem.

## Scope (v1)

- **Primed / zenithal-primed (monochrome) minis.** A primed model is already a
  shading map, so the tool reads highlight relief from the photo's own
  **luminance** (CLAHE-enhanced grayscale). Painted/coloured minis are future
  work — luminance there conflates dark paint with shadow.
- **Whole mini as one region.** Per-material regions (armour / blade / robe /
  skin) with their own techniques and palettes are on the roadmap.

## How it works

```
upload → mask (alpha fast-path, else depth fallback)
       → luminance light map
       → coverage-controlled curved banding (dark→light)
       → editable palette (LLM/default suggest, you tweak)
       → painted preview + legend + paint-along step images
```

## Install & run

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (use source .venv/bin/activate on *nix)
pip install -r requirements.txt
streamlit run app.py
```

First run downloads the depth model only if your upload has no alpha channel
(a background-removed PNG skips it and is fastest).

## Paint-along steps

For an N-layer plan you get, per layer:

- **Where to paint** — the zone for this layer in a bright marker (always
  visible, even for dark paints).
- **Apply across** — that zone in the actual paint colour.
- **Ends up here** — the slice that stays this colour after you highlight over it.

## Development

- Source: `src/mini_highlight_advisor/` — see `CLAUDE.md` for the module map and
  conventions.
- Tests: `.venv/Scripts/python -m pytest`
- Design specs and implementation plans live in `docs/superpowers/`.

## Roadmap

Per-material LLM regions · SAM-based masks · coloured-mini support · PDF export.
```

- [ ] **Step 2: Create `CLAUDE.md`**

Write the file with:

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: rewrite README and add CLAUDE.md for onboarding"
```

---

## Self-Review Notes

- **Spec coverage:** three-images-per-step + zone marker → Task 1 (`_zone_render`, `zone_rgb`) + Task 2 (3 columns); desaturate+dim background → Task 1 (`_desat_dim`, `_STEP_DIM`); accent constant → Task 1 (`_ACCENT`); outline dropped → Task 1 (delete `_outline_ring`/`_OUTLINE`, new test `test_no_pure_white_outline_pixels`); last-step 2-image → Task 1 (`exact_rgb None`) + Task 2 (2-column branch); all 7 spec test items → Task 1 Step 1 (updated + 4 new tests, plus retained v1.1 nesting/last-step/color-region tests); README + CLAUDE.md → Task 3. Scope-guarded items (paint_preview untouched, no toggles, no PDF) correctly absent.
- **Placeholder scan:** none — every code/doc step carries full literal content.
- **Type consistency:** `BandStep` field order (`index, zone_rgb, cumulative_rgb, exact_rgb, is_last`) and `per_band_images`/`_desat_dim`/`_zone_render`/`_render_step` signatures are identical across Tasks 1–2; app.py in Task 2 reads only fields defined in Task 1; constants (`_STEP_DIM`, `_ACCENT`, `_LUMA`) referenced consistently.
