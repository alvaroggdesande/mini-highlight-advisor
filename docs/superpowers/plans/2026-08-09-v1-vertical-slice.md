# Mini Highlight Advisor — v1 Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A working Streamlit app where you upload a primed-mini photo and get back a painted preview overlay + a paint-by-layer legend (role, paint name, coverage %), treating the whole mini as one region.

**Architecture:** A UI-agnostic core of small pure-ish modules (masking → lighting → banding → palette → overlay), orchestrated by a `pipeline.analyze()` function, with a thin Streamlit `app.py` on top. Logic is lifted from the validated spikes (`spikes/shading_spike.py`, `spikes/preview_spike.py`) and cleaned into tested functions. The banding step uses a coverage-controlled curve (top layers cover progressively less area) to fix the equal-width over-allocation found in the preview spike.

**Tech Stack:** Python 3.11, NumPy, OpenCV (`opencv-python`), Pillow, `transformers` + `torch` (CPU) for the depth-based mask fallback, Streamlit for the UI, pytest for tests.

## Global Constraints

- Python 3.11; Windows (`win32`). Use the existing `.venv` at repo root.
- No git worktrees. Work on branch `feat/v1-vertical-slice`; integrate via PR, not direct pushes to `main`.
- Core modules (`masking`, `lighting`, `banding`, `palette`, `overlay`, `pipeline`) MUST NOT import `streamlit`. Only `app.py` imports Streamlit.
- v1 scope: whole mini as ONE region. NO LLM, NO per-material regions (deferred to v2).
- v1 targets monochrome primed/undercoat photos. Do not attempt colored-mini handling.
- Package lives under `src/mini_highlight_advisor/`. Functions operate on NumPy `uint8` RGB arrays (H×W×3) and boolean masks (H×W), except `load_image` (path→arrays) and legend/panel builders (return `PIL.Image`).
- Default depth model: `depth-anything/Depth-Anything-V2-Small-hf`. Set env `HF_HUB_DISABLE_SYMLINKS_WARNING=1`.

---

## File Structure

- `src/mini_highlight_advisor/__init__.py` — package marker + version.
- `src/mini_highlight_advisor/palette.py` — `PaintColor`, `DEFAULT_PALETTE`, `role_names`, `default_coverage`, `coverage_pct`.
- `src/mini_highlight_advisor/banding.py` — `band_light` (coverage-controlled curved banding).
- `src/mini_highlight_advisor/lighting.py` — `luminance_light` (CLAHE + within-mask contrast stretch).
- `src/mini_highlight_advisor/masking.py` — `load_image`, `mask_from_alpha`, `mask_from_depthmap`, `mask_from_depth`, `compute_mask`.
- `src/mini_highlight_advisor/overlay.py` — `paint_preview`, `render_legend`, `compose_panel`.
- `src/mini_highlight_advisor/pipeline.py` — `HighlightResult`, `analyze`.
- `app.py` — thin Streamlit UI.
- `requirements.txt`, `pyproject.toml` — deps + pytest/package config.
- `tests/` — one test module per core module.

---

### Task 1: Project scaffold + config

**Files:**
- Create: `pyproject.toml`, `requirements.txt`, `src/mini_highlight_advisor/__init__.py`, `tests/__init__.py`, `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: importable package `mini_highlight_advisor` with `__version__: str`.

- [ ] **Step 1: Create branch**

```bash
git -C C:/Users/ag/alvaro/git/mini-highlight-advisor checkout -b feat/v1-vertical-slice
```

- [ ] **Step 2: Write `requirements.txt`**

```
numpy
opencv-python
pillow
transformers
torch
streamlit
pytest
```

- [ ] **Step 3: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "mini-highlight-advisor"
version = "0.1.0"
requires-python = ">=3.11"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 4: Write `src/mini_highlight_advisor/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 5: Write `tests/__init__.py`** (empty file) and **`tests/test_smoke.py`**

```python
import mini_highlight_advisor as mha


def test_package_imports_with_version():
    assert isinstance(mha.__version__, str)
    assert mha.__version__
```

- [ ] **Step 6: Install deps into the existing venv**

Run: `C:/Users/ag/alvaro/git/mini-highlight-advisor/.venv/Scripts/python.exe -m pip install streamlit pytest`
(torch/transformers/opencv/pillow/numpy are already installed from the spikes.)

- [ ] **Step 7: Run smoke test**

Run: `C:/Users/ag/alvaro/git/mini-highlight-advisor/.venv/Scripts/python.exe -m pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml requirements.txt src tests
git commit -m "chore: scaffold package + pytest config"
```

---

### Task 2: Palette model + roles + coverage

**Files:**
- Create: `src/mini_highlight_advisor/palette.py`, `tests/test_palette.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `PaintColor(name: str, hex: str)` dataclass with property `rgb -> np.ndarray` (float32, shape (3,), 0–255).
  - `DEFAULT_PALETTE: list[PaintColor]` (5 entries, dark→light).
  - `role_names(n: int) -> list[str]`.
  - `default_coverage(n: int) -> list[float]` (decreasing, sums to 1.0).
  - `coverage_pct(bands: np.ndarray, mask: np.ndarray, n: int) -> list[float]` (percent of masked pixels per band index 0..n-1).

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from mini_highlight_advisor.palette import (
    PaintColor, DEFAULT_PALETTE, role_names, default_coverage, coverage_pct,
)


def test_paintcolor_hex_to_rgb():
    assert np.allclose(PaintColor("White", "#ffffff").rgb, [255, 255, 255])
    assert np.allclose(PaintColor("Black", "#000000").rgb, [0, 0, 0])


def test_default_palette_is_five_dark_to_light():
    assert len(DEFAULT_PALETTE) == 5
    lums = [c.rgb.mean() for c in DEFAULT_PALETTE]
    assert lums == sorted(lums)  # ascending brightness


def test_role_names_known_and_generic():
    assert role_names(5) == ["Shadow", "Base", "Midtone", "Highlight", "Edge Highlight"]
    assert role_names(2) == ["Layer 1", "Layer 2"]


def test_default_coverage_decreasing_and_normalized():
    cov = default_coverage(5)
    assert abs(sum(cov) - 1.0) < 1e-6
    assert cov == sorted(cov, reverse=True)  # shadow largest, edge smallest


def test_coverage_pct_counts_within_mask():
    bands = np.array([[0, 1], [1, -1]])
    mask = np.array([[True, True], [True, False]])
    pct = coverage_pct(bands, mask, 2)
    assert abs(pct[0] - 100 / 3) < 1e-6
    assert abs(pct[1] - 200 / 3) < 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_palette.py -v`
Expected: FAIL (ModuleNotFoundError: mini_highlight_advisor.palette)

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PaintColor:
    name: str
    hex: str

    @property
    def rgb(self) -> np.ndarray:
        h = self.hex.lstrip("#")
        return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


DEFAULT_PALETTE = [
    PaintColor("Abaddon Black", "#14151a"),
    PaintColor("Leadbelcher", "#4b4f54"),
    PaintColor("Dawnstone", "#71767b"),
    PaintColor("Administratum Grey", "#a9adb0"),
    PaintColor("White Scar", "#eef0f2"),
]

_ROLES = {
    3: ["Shadow", "Base", "Highlight"],
    4: ["Shadow", "Base", "Midtone", "Highlight"],
    5: ["Shadow", "Base", "Midtone", "Highlight", "Edge Highlight"],
}


def role_names(n: int) -> list[str]:
    return _ROLES.get(n, [f"Layer {i + 1}" for i in range(n)])


def default_coverage(n: int) -> list[float]:
    # Linear decreasing weights: shadow widest, edge highlight thinnest.
    weights = list(range(n, 0, -1))
    total = sum(weights)
    return [w / total for w in weights]


def coverage_pct(bands: np.ndarray, mask: np.ndarray, n: int) -> list[float]:
    total = int(mask.sum())
    if total == 0:
        return [0.0] * n
    return [100.0 * int(((bands == b) & mask).sum()) / total for b in range(n)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_palette.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/palette.py tests/test_palette.py
git commit -m "feat: palette model, roles, coverage helpers"
```

---

### Task 3: Coverage-controlled curved banding

**Files:**
- Create: `src/mini_highlight_advisor/banding.py`, `tests/test_banding.py`

**Interfaces:**
- Consumes: `default_coverage` (from `palette`).
- Produces: `band_light(light: np.ndarray, mask: np.ndarray, coverage: list[float]) -> np.ndarray`
  returns int32 array; band index `0..len(coverage)-1` inside mask (0 = darkest), `-1` outside.
  Band boundaries are quantiles of the in-mask light values chosen so band `b` covers ≈ `coverage[b]`
  of the masked pixels — this is what makes upper (highlight) bands cover less area.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from mini_highlight_advisor.banding import band_light


def test_band_light_respects_target_coverage():
    # Uniform gradient over a full mask -> coverage should match targets closely.
    light = np.tile(np.linspace(0, 1, 1000, dtype=np.float32), (10, 1))
    mask = np.ones_like(light, dtype=bool)
    coverage = [0.4, 0.3, 0.2, 0.1]
    bands = band_light(light, mask, coverage)
    total = mask.sum()
    for b, target in enumerate(coverage):
        frac = (bands == b).sum() / total
        assert abs(frac - target) < 0.02


def test_band_light_darkest_is_zero_brightest_is_last():
    light = np.tile(np.linspace(0, 1, 100, dtype=np.float32), (5, 1))
    mask = np.ones_like(light, dtype=bool)
    bands = band_light(light, mask, [0.5, 0.5])
    assert bands[0, 0] == 0        # darkest pixel -> band 0
    assert bands[0, -1] == 1       # brightest pixel -> last band


def test_band_light_marks_outside_mask_as_minus_one():
    light = np.zeros((2, 2), dtype=np.float32)
    mask = np.array([[True, False], [True, True]])
    bands = band_light(light, mask, [1.0])
    assert bands[0, 1] == -1
    assert set(np.unique(bands[mask])) <= {0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_banding.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import numpy as np


def band_light(light: np.ndarray, mask: np.ndarray, coverage: list[float]) -> np.ndarray:
    n = len(coverage)
    bands = np.full(light.shape, -1, dtype=np.int32)
    vals = light[mask]
    if vals.size == 0:
        return bands
    # Cumulative target fractions give the quantile cut points (interior boundaries only).
    cum = np.cumsum(coverage)[:-1]
    edges = np.quantile(vals, cum)
    idx = np.digitize(light, edges)  # 0..n-1
    bands[mask] = idx[mask].astype(np.int32)
    return bands
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_banding.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/banding.py tests/test_banding.py
git commit -m "feat: coverage-controlled curved banding"
```

---

### Task 4: Luminance light map

**Files:**
- Create: `src/mini_highlight_advisor/lighting.py`, `tests/test_lighting.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `luminance_light(rgb: np.ndarray, mask: np.ndarray, clip_limit: float = 3.0) -> np.ndarray`
  returns float32 in [0,1] inside the mask (CLAHE-enhanced luminance, contrast-stretched to the
  2nd–98th percentile within the mask); 0.0 outside the mask.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from mini_highlight_advisor.lighting import luminance_light


def test_luminance_zero_outside_mask():
    rgb = np.full((8, 8, 3), 128, dtype=np.uint8)
    mask = np.zeros((8, 8), dtype=bool)
    mask[2:6, 2:6] = True
    out = luminance_light(rgb, mask)
    assert out.shape == (8, 8)
    assert np.all(out[~mask] == 0.0)


def test_luminance_brighter_pixels_map_higher():
    # Left half dark, right half bright, all masked.
    rgb = np.zeros((16, 16, 3), dtype=np.uint8)
    rgb[:, 8:] = 200
    mask = np.ones((16, 16), dtype=bool)
    out = luminance_light(rgb, mask)
    assert out[:, 12].mean() > out[:, 3].mean()


def test_luminance_in_unit_range():
    rng = np.random.default_rng(0)
    rgb = rng.integers(0, 256, size=(20, 20, 3), dtype=np.uint8)
    mask = np.ones((20, 20), dtype=bool)
    out = luminance_light(rgb, mask)
    assert out.min() >= 0.0 and out.max() <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_lighting.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import cv2
import numpy as np


def luminance_light(rgb: np.ndarray, mask: np.ndarray, clip_limit: float = 3.0) -> np.ndarray:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    gray = clahe.apply(gray).astype(np.float32)
    inside = gray[mask]
    if inside.size == 0:
        return np.zeros(gray.shape, dtype=np.float32)
    lo, hi = np.percentile(inside, 2), np.percentile(inside, 98)
    light = np.clip((gray - lo) / (hi - lo + 1e-9), 0.0, 1.0).astype(np.float32)
    light[~mask] = 0.0
    return light
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_lighting.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/lighting.py tests/test_lighting.py
git commit -m "feat: luminance light map (CLAHE + masked stretch)"
```

---

### Task 5: Masking (alpha fast-path + depth fallback)

**Files:**
- Create: `src/mini_highlight_advisor/masking.py`, `tests/test_masking.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `load_image(path: str, max_side: int = 768) -> tuple[np.ndarray, np.ndarray | None]`
    returns `(rgb uint8 H×W×3 composited over black, alpha uint8 H×W or None)`, both downscaled so
    the longest side ≤ `max_side`.
  - `mask_from_alpha(alpha: np.ndarray, thresh: int = 128) -> np.ndarray` (bool; largest opaque blob, holes closed).
  - `mask_from_depthmap(depth: np.ndarray) -> np.ndarray` (bool; Otsu on a normalized depth map, largest blob, closed).
  - `mask_from_depth(rgb: np.ndarray, model: str = "depth-anything/Depth-Anything-V2-Small-hf") -> np.ndarray` (bool; runs the model then `mask_from_depthmap`).
  - `compute_mask(rgb: np.ndarray, alpha: np.ndarray | None, alpha_thresh: int = 128) -> np.ndarray`
    (bool; uses alpha when present, else depth).

**Note:** unit-test the pure pieces (`mask_from_alpha`, `mask_from_depthmap`). `mask_from_depth` and `load_image` are exercised in Task 7's pipeline test on a real fixture image; do not download the model in unit tests.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from mini_highlight_advisor.masking import mask_from_alpha, mask_from_depthmap


def test_mask_from_alpha_keeps_opaque_largest_blob():
    alpha = np.zeros((20, 20), dtype=np.uint8)
    alpha[5:15, 5:15] = 255           # big opaque square
    alpha[0:2, 0:2] = 255             # tiny speck (should be dropped)
    m = mask_from_alpha(alpha)
    assert m[10, 10]
    assert not m[0, 0]


def test_mask_from_alpha_drops_semi_transparent_halo():
    alpha = np.full((10, 10), 100, dtype=np.uint8)  # below default thresh 128
    alpha[3:7, 3:7] = 255
    m = mask_from_alpha(alpha)
    assert m[5, 5]
    assert not m[0, 0]


def test_mask_from_depthmap_separates_near_foreground():
    depth = np.zeros((20, 20), dtype=np.float32)   # far background
    depth[5:15, 5:15] = 1.0                         # near figure
    m = mask_from_depthmap(depth)
    assert m[10, 10]
    assert not m[0, 0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_masking.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def _largest_blob(binary: np.ndarray) -> np.ndarray:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if n > 1:
        biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        binary = np.where(labels == biggest, 255, 0).astype(np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    return binary > 0


def mask_from_alpha(alpha: np.ndarray, thresh: int = 128) -> np.ndarray:
    return _largest_blob((alpha > thresh).astype(np.uint8) * 255)


def mask_from_depthmap(depth: np.ndarray) -> np.ndarray:
    d = depth.astype(np.float32)
    d = (d - d.min()) / (d.ptp() + 1e-9) if np.ptp(d) > 1e-9 else np.zeros_like(d)
    d8 = (d * 255).astype(np.uint8)
    _, binary = cv2.threshold(d8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return _largest_blob(binary)


def mask_from_depth(rgb: np.ndarray, model: str = "depth-anything/Depth-Anything-V2-Small-hf") -> np.ndarray:
    from transformers import pipeline

    pipe = pipeline(task="depth-estimation", model=model)
    depth = np.asarray(pipe(Image.fromarray(rgb))["depth"], dtype=np.float32)
    return mask_from_depthmap(depth)


def load_image(path: str, max_side: int = 768) -> tuple[np.ndarray, np.ndarray | None]:
    im = Image.open(path)
    has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    if has_alpha:
        rgba = im.convert("RGBA")
        rgba.thumbnail((max_side, max_side))
        arr = np.asarray(rgba)
        alpha = arr[..., 3].copy()
        bg = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
        rgb = np.asarray(Image.alpha_composite(bg, rgba).convert("RGB"))
        return rgb, alpha
    rgb_im = im.convert("RGB")
    rgb_im.thumbnail((max_side, max_side))
    return np.asarray(rgb_im), None


def compute_mask(rgb: np.ndarray, alpha: np.ndarray | None, alpha_thresh: int = 128) -> np.ndarray:
    if alpha is not None:
        return mask_from_alpha(alpha, alpha_thresh)
    return mask_from_depth(rgb)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_masking.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/masking.py tests/test_masking.py
git commit -m "feat: masking (alpha fast-path + depth fallback)"
```

---

### Task 6: Overlay + legend + panel

**Files:**
- Create: `src/mini_highlight_advisor/overlay.py`, `tests/test_overlay.py`

**Interfaces:**
- Consumes: nothing (receives colors/names/roles/coverage as plain lists).
- Produces:
  - `paint_preview(rgb: np.ndarray, bands: np.ndarray, mask: np.ndarray, colors: list[np.ndarray], alpha: float = 0.78) -> np.ndarray`
    (uint8 H×W×3: each band recolored with its paint color; background darkened ×0.25).
  - `render_legend(colors: list[np.ndarray], names: list[str], roles: list[str], coverage: list[float], height: int, width: int = 430) -> PIL.Image.Image`.
  - `compose_panel(original_rgb: np.ndarray, preview_rgb: np.ndarray, legend: PIL.Image.Image) -> PIL.Image.Image` (horizontal stack).

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from PIL import Image
from mini_highlight_advisor.overlay import paint_preview, render_legend, compose_panel


def test_paint_preview_colors_bands_and_darkens_background():
    rgb = np.full((4, 4, 3), 100, dtype=np.uint8)
    bands = np.array([[0, 1, 1, 1], [-1, -1, -1, -1], [0, 0, 1, 1], [0, 0, 1, 1]], dtype=np.int32)
    mask = bands >= 0
    colors = [np.array([255, 0, 0], np.float32), np.array([0, 0, 255], np.float32)]
    out = paint_preview(rgb, bands, mask, colors, alpha=1.0)
    assert out.dtype == np.uint8
    assert tuple(out[0, 0]) == (255, 0, 0)      # band 0 -> red
    assert tuple(out[0, 1]) == (0, 0, 255)      # band 1 -> blue
    assert out[1, 0].sum() < rgb[1, 0].sum()    # background darkened


def test_render_legend_dimensions():
    img = render_legend(
        colors=[np.array([20, 20, 20], np.float32), np.array([230, 230, 230], np.float32)],
        names=["Abaddon Black", "White Scar"],
        roles=["Shadow", "Highlight"],
        coverage=[70.0, 30.0],
        height=400,
    )
    assert isinstance(img, Image.Image)
    assert img.size == (430, 400)


def test_compose_panel_width_is_sum():
    a = np.zeros((100, 50, 3), np.uint8)
    b = np.zeros((100, 60, 3), np.uint8)
    legend = Image.new("RGB", (430, 100))
    panel = compose_panel(a, b, legend)
    assert panel.width == 50 + 60 + 430 + 20  # two 10px gaps
    assert panel.height == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_overlay.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_COVERAGE_NOTES = {
    "Shadow": "deepest recesses",
    "Base": "the main body of the surface",
    "Midtone": "flat, gently-lit panels",
    "Highlight": "raised areas facing the light",
    "Edge Highlight": "sharpest top edges only",
}


def paint_preview(rgb, bands, mask, colors, alpha: float = 0.78) -> np.ndarray:
    base = rgb.astype(np.float32)
    out = base.copy()
    out[~mask] = out[~mask] * 0.25
    for b, color in enumerate(colors):
        m = (bands == b) & mask
        out[m] = (1 - alpha) * base[m] + alpha * color
    return np.clip(out, 0, 255).astype(np.uint8)


def _font(size: int):
    for path in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render_legend(colors, names, roles, coverage, height: int, width: int = 430) -> Image.Image:
    img = Image.new("RGB", (width, height), (26, 27, 32))
    d = ImageDraw.Draw(img)
    title_f, role_f, body_f, small_f = _font(26), _font(21), _font(18), _font(15)
    d.text((20, 18), "Highlight plan", font=title_f, fill=(240, 240, 245))
    d.text((20, 52), "dark to light  (paint in this order)", font=small_f, fill=(150, 152, 160))
    n = len(colors)
    top, sw = 92, 54
    row_h = min(96, (height - top - 16) // max(n, 1))
    for i in range(n):
        y = top + i * row_h
        rgb = tuple(int(v) for v in colors[i])
        d.rectangle([20, y, 20 + sw, y + sw], fill=rgb, outline=(70, 72, 80), width=2)
        d.text((20, y + sw + 2), str(i + 1), font=small_f, fill=(150, 152, 160))
        tx = 20 + sw + 18
        d.text((tx, y), roles[i], font=role_f, fill=(235, 236, 240))
        d.text((tx, y + 26), names[i], font=body_f, fill=(190, 192, 200))
        note = _COVERAGE_NOTES.get(roles[i], "")
        d.text((tx, y + 50), f"~{coverage[i]:.0f}% - {note}", font=small_f, fill=(150, 152, 160))
    return img


def compose_panel(original_rgb, preview_rgb, legend: Image.Image, gap: int = 10) -> Image.Image:
    imgs = [Image.fromarray(original_rgb), Image.fromarray(preview_rgb), legend]
    h = max(i.height for i in imgs)
    w = sum(i.width for i in imgs) + gap * (len(imgs) - 1)
    canvas = Image.new("RGB", (w, h), (26, 27, 32))
    x = 0
    for im in imgs:
        canvas.paste(im, (x, (h - im.height) // 2))
        x += im.width + gap
    return canvas
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_overlay.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/overlay.py tests/test_overlay.py
git commit -m "feat: paint preview, legend, panel composition"
```

---

### Task 7: Pipeline orchestration

**Files:**
- Create: `src/mini_highlight_advisor/pipeline.py`, `tests/test_pipeline.py`
- Test fixture: use `spikes/input/WhatsApp_Image_2026-08-09_at_14.04.40-removebg-preview.png` (alpha PNG → no model download).

**Interfaces:**
- Consumes: `palette` (`PaintColor`, `role_names`, `default_coverage`, `coverage_pct`), `banding.band_light`, `lighting.luminance_light`, `masking` (`load_image`, `compute_mask`), `overlay` (`paint_preview`, `render_legend`, `compose_panel`).
- Produces:
  - `HighlightResult` dataclass: `mask: np.ndarray`, `light: np.ndarray`, `bands: np.ndarray`, `coverage: list[float]`, `roles: list[str]`, `preview_rgb: np.ndarray`, `panel: PIL.Image.Image`.
  - `analyze(rgb: np.ndarray, alpha: np.ndarray | None, palette: list[PaintColor]) -> HighlightResult`
    (n_bands is inferred as `len(palette)`).

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from mini_highlight_advisor.masking import load_image
from mini_highlight_advisor.palette import DEFAULT_PALETTE, coverage_pct
from mini_highlight_advisor.pipeline import analyze, HighlightResult

FIXTURE = "spikes/input/WhatsApp_Image_2026-08-09_at_14.04.40-removebg-preview.png"


def test_analyze_end_to_end_on_alpha_png():
    rgb, alpha = load_image(FIXTURE)
    result = analyze(rgb, alpha, DEFAULT_PALETTE)
    assert isinstance(result, HighlightResult)
    # Every band index present within the mask is valid.
    assert set(np.unique(result.bands[result.mask])) <= set(range(len(DEFAULT_PALETTE)))
    # Coverage sums to ~100% and is reported per band.
    assert len(result.coverage) == len(DEFAULT_PALETTE)
    assert abs(sum(result.coverage) - 100.0) < 0.5
    # Preview matches image dims; panel is wider (has legend).
    assert result.preview_rgb.shape == rgb.shape
    assert result.panel.width > rgb.shape[1]


def test_analyze_edge_band_covers_less_than_shadow():
    rgb, alpha = load_image(FIXTURE)
    result = analyze(rgb, alpha, DEFAULT_PALETTE)
    assert result.coverage[-1] < result.coverage[0]  # curved banding: edge < shadow
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from .banding import band_light
from .lighting import luminance_light
from .masking import compute_mask
from .overlay import compose_panel, paint_preview, render_legend
from .palette import PaintColor, coverage_pct, default_coverage, role_names


@dataclass
class HighlightResult:
    mask: np.ndarray
    light: np.ndarray
    bands: np.ndarray
    coverage: list[float]
    roles: list[str]
    preview_rgb: np.ndarray
    panel: Image.Image


def analyze(rgb: np.ndarray, alpha: np.ndarray | None, palette: list[PaintColor]) -> HighlightResult:
    n = len(palette)
    colors = [p.rgb for p in palette]
    names = [p.name for p in palette]
    roles = role_names(n)

    mask = compute_mask(rgb, alpha)
    light = luminance_light(rgb, mask)
    bands = band_light(light, mask, default_coverage(n))
    coverage = coverage_pct(bands, mask, n)

    preview_rgb = paint_preview(rgb, bands, mask, colors)
    legend = render_legend(colors, names, roles, coverage, height=preview_rgb.shape[0])
    panel = compose_panel(rgb, preview_rgb, legend)

    return HighlightResult(mask, light, bands, coverage, roles, preview_rgb, panel)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/mini_highlight_advisor/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline.analyze orchestration + end-to-end test"
```

---

### Task 8: Thin Streamlit app

**Files:**
- Create: `app.py`

**Interfaces:**
- Consumes: `masking.load_image`, `palette` (`DEFAULT_PALETTE`, `PaintColor`), `pipeline.analyze`.
- Produces: a runnable Streamlit app (no unit tests; manual verification).

- [ ] **Step 1: Write `app.py`**

```python
import os
import tempfile

import streamlit as st

from mini_highlight_advisor.masking import load_image
from mini_highlight_advisor.palette import DEFAULT_PALETTE, PaintColor
from mini_highlight_advisor.pipeline import analyze

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

st.set_page_config(page_title="Mini Highlight Advisor", layout="wide")
st.title("Mini Highlight Advisor")
st.caption(
    "Upload a photo of a primed miniature (background-removed PNG is fastest). "
    "You'll get a painted preview + a paint-by-layer plan. Best on a well-lit, "
    "ideally zenithal-primed model."
)

n = st.sidebar.slider("Number of layers", 3, 5, 5)
st.sidebar.markdown("**Palette** (dark to light)")
palette = []
for i in range(n):
    default = DEFAULT_PALETTE[min(i, len(DEFAULT_PALETTE) - 1)]
    c1, c2 = st.sidebar.columns([2, 1])
    name = c1.text_input(f"Layer {i + 1} name", value=default.name, key=f"name{i}")
    hexv = c2.color_picker(f"Layer {i + 1}", value=default.hex, key=f"hex{i}")
    palette.append(PaintColor(name, hexv))

uploaded = st.file_uploader("Mini photo", type=["png", "jpg", "jpeg"])
if uploaded is not None:
    suffix = os.path.splitext(uploaded.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getbuffer())
        tmp_path = tmp.name
    with st.spinner("Analyzing (first run downloads the depth model if no alpha channel)..."):
        rgb, alpha = load_image(tmp_path)
        result = analyze(rgb, alpha, palette)
    st.image(result.panel, caption="Original | Painted preview | Highlight plan", use_column_width=True)
    st.subheader("Layer guide (paint dark to light)")
    for role, paint, cov in zip(result.roles, palette, result.coverage):
        st.markdown(f"**{role}** - {paint.name}  ·  ~{cov:.0f}% of the model")
    os.unlink(tmp_path)
```

- [ ] **Step 2: Manual verification**

Run: `.venv/Scripts/python.exe -m streamlit run app.py`
Then in the browser:
1. Upload `spikes/input/Mini-Imprimada.jpg` (JPG → exercises the depth-mask fallback).
2. Confirm a 3-panel image appears (original | painted preview | legend) and the layer guide lists 5 layers with coverage.
3. Change a palette color in the sidebar and confirm the preview updates.
4. Upload one of the `WhatsApp_*.png` files and confirm it renders faster (alpha fast-path, no model).

Expected: painted preview shows dark recesses → bright edges; legend readable.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: thin Streamlit UI for upload -> preview + plan"
```

---

## Self-Review

**Spec coverage (vertical-slice subset):**
- Two outputs (overlay + written guide) → panel image (Task 6/7) + layer guide list (Task 8). ✅ (annotated overlay + text; full LLM prose guide deferred with regions.)
- Depth-for-mask + luminance-for-relief (Section 6) → `masking` + `lighting` (Tasks 4–5). ✅
- Own the masking, alpha as fast-path only → `compute_mask` alpha/depth split (Task 5). ✅
- Curved banding (upper bands thinner) → `band_light` coverage-controlled quantiles (Task 3), asserted in Task 7. ✅
- Palette suggest-then-edit → `DEFAULT_PALETTE` + sidebar editing (Tasks 2, 8). ✅
- Recommended band count, user-editable → slider 3–5 (Task 8); per-region recommendation deferred with regions. ✅ (scoped)
- UI-agnostic core → core modules import no Streamlit (Global Constraints). ✅
- Region-centric / LLM regions → **explicitly deferred to v2** per chosen "thin vertical slice" scope. Documented, not a gap.

**Placeholder scan:** No TBD/TODO; every code step contains full implementations and concrete test code. ✅

**Type consistency:** `band_light(light, mask, coverage)` used identically in Tasks 3 and 7; `paint_preview`/`render_legend`/`compose_panel` signatures match between Tasks 6 and 7; `load_image`/`compute_mask` signatures match between Tasks 5, 7, 8; `HighlightResult` fields produced in Task 7 are consumed by the same names in Task 8. ✅

**Deferred (documented, not gaps):** LLM per-material regions, per-region band curves, manual region correction, PDF export, colored-mini support, SAM masks — all v2+ per spec Sections 7–8.
