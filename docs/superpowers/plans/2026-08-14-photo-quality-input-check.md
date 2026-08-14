# Photo-Quality Guide + Input Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Warn the user, with actionable advice, when an uploaded mini photo will produce a poor highlight plan (flat lighting, clipped exposure, small framing, soft focus), plus surface a static shooting guide.

**Architecture:** One new pure, Streamlit-free module `input_check.py` measures the raw grayscale inside the already-computed mask and returns a list of `CheckResult` records (each carrying a measured value + an actionable `detail` string). `app.py` renders these as an always-on, non-blocking "Photo quality" panel with the shooting guide in an expander. The mask is computed once (via existing `compute_mask`) and shared with the render path — no second depth-model run.

**Tech Stack:** Python 3.11, numpy, opencv (`cv2`), Streamlit; pytest for tests. All already in the repo's `.venv`.

## Global Constraints

- **Offline / free / zero-LLM** — every check is a local numpy/opencv measurement. No network, no API.
- **Advisory / non-blocking** — the panel never gates the highlight plan; warnings sit above a working result.
- **Pure core** — `input_check.py` imports no Streamlit; it takes arrays and returns dataclasses. Only `app.py` touches Streamlit.
- **Measure raw grayscale, not `lighting.luminance_light`** — CLAHE + percentile-stretch would hide flat/clipped exposure.
- **Takes the already-computed mask**, never recomputes it (avoids a second depth-model run).
- **Thresholds are named module constants** with a one-line comment on the reasoning; tuning later is a one-line edit.
- **Every `detail` string is actionable** — observation + concrete fix, or a short confirmation when passing. Never a bare "poor".
- **Tests:** `.venv/Scripts/python -m pytest`. Feature branch is `feat/photo-quality-input-check` (already checked out); commit per task, never on `main`.

---

### Task 1: Module scaffold + lighting check

**Files:**
- Create: `src/mini_highlight_advisor/input_check.py`
- Test: `tests/test_input_check.py`

**Interfaces:**
- Consumes: nothing (leaf module).
- Produces:
  - `@dataclass CheckResult(id: str, label: str, ok: bool, value: float, detail: str)`
  - `check_input(rgb: np.ndarray, mask: np.ndarray) -> list[CheckResult]`
  - `_to_gray(rgb: np.ndarray) -> np.ndarray` (uint8 (H,W))
  - `_check_lighting(gray: np.ndarray, mask: np.ndarray) -> CheckResult`
  - Constant `FLAT_SPREAD_MAX = 60`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_input_check.py
import numpy as np
from mini_highlight_advisor.input_check import check_input, CheckResult


def _full_mask(h, w):
    return np.ones((h, w), dtype=bool)


def test_flat_image_fails_lighting_with_advice():
    # Uniform mid-grey -> no tonal spread -> lighting must fail.
    rgb = np.full((200, 200, 3), 128, dtype=np.uint8)
    results = check_input(rgb, _full_mask(200, 200))
    lighting = next(r for r in results if r.id == "lighting")
    assert lighting.ok is False
    assert "flat" in lighting.detail.lower()
    assert "raking" in lighting.detail.lower()  # actionable fix present


def test_high_contrast_gradient_passes_lighting():
    grad = np.tile(np.linspace(0, 255, 200, dtype=np.uint8), (200, 1))
    rgb = np.stack([grad, grad, grad], axis=-1)
    results = check_input(rgb, _full_mask(200, 200))
    lighting = next(r for r in results if r.id == "lighting")
    assert lighting.ok is True
    assert isinstance(lighting, CheckResult)


def test_check_input_returns_lighting_first():
    rgb = np.full((50, 50, 3), 128, dtype=np.uint8)
    results = check_input(rgb, _full_mask(50, 50))
    assert results[0].id == "lighting"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_input_check.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mini_highlight_advisor.input_check'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/mini_highlight_advisor/input_check.py
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# --- Tuning constants (raw grey 0-255 inside the mask) --------------------
FLAT_SPREAD_MAX = 60  # p95-p5 below this => lighting too flat to read form


@dataclass
class CheckResult:
    id: str        # "lighting" | "exposure" | "focus" | "resolution"
    label: str     # human label shown in the panel
    ok: bool
    value: float   # measured number, surfaced to the user
    detail: str    # observation + concrete fix; never a bare verdict


def _to_gray(rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def _check_lighting(gray: np.ndarray, mask: np.ndarray) -> CheckResult:
    inside = gray[mask]
    p5, p95 = np.percentile(inside, [5, 95])
    spread = float(p95 - p5)
    ok = spread >= FLAT_SPREAD_MAX
    if ok:
        detail = "Good tonal range across the mini."
    else:
        detail = (
            f"Lighting is flat (spread {spread:.0f}/255) — light the mini with a "
            "single raking light from one side (~45°) and turn off any on-axis / "
            "built-in flash."
        )
    return CheckResult("lighting", "Lighting", ok, spread, detail)


def check_input(rgb: np.ndarray, mask: np.ndarray) -> list[CheckResult]:
    gray = _to_gray(rgb)
    return [
        _check_lighting(gray, mask),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_input_check.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/input_check.py tests/test_input_check.py
git commit -m "feat: input_check module scaffold + lighting flatness check"
```

---

### Task 2: Exposure clipping check

**Files:**
- Modify: `src/mini_highlight_advisor/input_check.py`
- Test: `tests/test_input_check.py`

**Interfaces:**
- Consumes: `CheckResult`, `_to_gray`, `check_input` from Task 1.
- Produces:
  - `_check_exposure(gray: np.ndarray, mask: np.ndarray) -> CheckResult` (id `"exposure"`)
  - Constants `CRUSH_VALUE = 4`, `CRUSH_FRAC_MAX = 0.25`, `BLOWN_VALUE = 250`, `BLOWN_FRAC_MAX = 0.05`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_input_check.py
def test_mostly_black_fails_exposure_crushed():
    rgb = np.zeros((200, 200, 3), dtype=np.uint8)  # all crushed to black
    results = check_input(rgb, _full_mask(200, 200))
    exposure = next(r for r in results if r.id == "exposure")
    assert exposure.ok is False
    assert "crushed" in exposure.detail.lower()
    assert "raise exposure" in exposure.detail.lower()


def test_mostly_white_fails_exposure_blown():
    rgb = np.full((200, 200, 3), 255, dtype=np.uint8)  # all blown out
    results = check_input(rgb, _full_mask(200, 200))
    exposure = next(r for r in results if r.id == "exposure")
    assert exposure.ok is False
    assert "blown" in exposure.detail.lower()
    assert "lower exposure" in exposure.detail.lower()


def test_balanced_gradient_passes_exposure():
    grad = np.tile(np.linspace(20, 235, 200, dtype=np.uint8), (200, 1))
    rgb = np.stack([grad, grad, grad], axis=-1)
    results = check_input(rgb, _full_mask(200, 200))
    exposure = next(r for r in results if r.id == "exposure")
    assert exposure.ok is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_input_check.py -k exposure -v`
Expected: FAIL — `StopIteration` (no `CheckResult` with id `"exposure"` yet)

- [ ] **Step 3: Write minimal implementation**

Add the constants near `FLAT_SPREAD_MAX`:

```python
CRUSH_VALUE = 4          # grey <= this counts as crushed-to-black
CRUSH_FRAC_MAX = 0.25    # >25% crushed => shadow detail lost
BLOWN_VALUE = 250        # grey >= this counts as blown-out
BLOWN_FRAC_MAX = 0.05    # >5% blown => highlight detail lost
```

Add the check function:

```python
def _check_exposure(gray: np.ndarray, mask: np.ndarray) -> CheckResult:
    inside = gray[mask]
    crushed = float(np.mean(inside <= CRUSH_VALUE))
    blown = float(np.mean(inside >= BLOWN_VALUE))
    crushed_bad = crushed > CRUSH_FRAC_MAX
    blown_bad = blown > BLOWN_FRAC_MAX
    ok = not (crushed_bad or blown_bad)
    parts = []
    if crushed_bad:
        parts.append(
            f"{crushed * 100:.0f}% of the mini is crushed to black — raise exposure "
            "or add a fill light; shadow detail is lost."
        )
    if blown_bad:
        parts.append(
            f"{blown * 100:.0f}% is blown out — lower exposure and diffuse the light."
        )
    detail = " ".join(parts) if parts else (
        "Exposure looks balanced — shadows and highlights both hold detail."
    )
    return CheckResult("exposure", "Exposure", ok, max(crushed, blown), detail)
```

Extend `check_input` to append it:

```python
    return [
        _check_lighting(gray, mask),
        _check_exposure(gray, mask),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_input_check.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/input_check.py tests/test_input_check.py
git commit -m "feat: exposure clipping check (crushed / blown)"
```

---

### Task 3: Focus / sharpness check

**Files:**
- Modify: `src/mini_highlight_advisor/input_check.py`
- Test: `tests/test_input_check.py`

**Interfaces:**
- Consumes: `CheckResult`, `_to_gray`, `check_input` from earlier tasks.
- Produces:
  - `_check_focus(gray: np.ndarray, mask: np.ndarray) -> CheckResult` (id `"focus"`)
  - Constant `MIN_FOCUS_VAR = 100.0`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_input_check.py
import cv2  # add to existing imports at top of file


def test_sharp_checkerboard_passes_focus():
    tile = np.kron(np.array([[0, 1], [1, 0]]), np.ones((10, 10)))
    board = np.tile(tile, (10, 10)).astype(np.uint8) * 255
    rgb = np.stack([board, board, board], axis=-1)
    results = check_input(rgb, _full_mask(*board.shape))
    focus = next(r for r in results if r.id == "focus")
    assert focus.ok is True


def test_blurred_image_fails_focus_with_advice():
    tile = np.kron(np.array([[0, 1], [1, 0]]), np.ones((10, 10)))
    board = np.tile(tile, (10, 10)).astype(np.uint8) * 255
    blurred = cv2.GaussianBlur(board, (0, 0), sigmaX=8)
    rgb = np.stack([blurred, blurred, blurred], axis=-1)
    results = check_input(rgb, _full_mask(*blurred.shape))
    focus = next(r for r in results if r.id == "focus")
    assert focus.ok is False
    assert "focus" in focus.detail.lower()
    assert "steady" in focus.detail.lower()  # actionable fix present
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_input_check.py -k focus -v`
Expected: FAIL — `StopIteration` (no `CheckResult` with id `"focus"` yet)

- [ ] **Step 3: Write minimal implementation**

Add the constant:

```python
MIN_FOCUS_VAR = 100.0  # variance of Laplacian below this => soft / out of focus
```

Add the check function:

```python
def _check_focus(gray: np.ndarray, mask: np.ndarray) -> CheckResult:
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    var = float(lap[mask].var())
    ok = var >= MIN_FOCUS_VAR
    if ok:
        detail = "Sharp."
    else:
        detail = (
            "Photo looks soft / out of focus — refocus on the mini and hold steady "
            "(use a timer or brace your hands)."
        )
    return CheckResult("focus", "Focus", ok, var, detail)
```

Extend `check_input`:

```python
    return [
        _check_lighting(gray, mask),
        _check_exposure(gray, mask),
        _check_focus(gray, mask),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_input_check.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/input_check.py tests/test_input_check.py
git commit -m "feat: focus/sharpness check (Laplacian variance)"
```

---

### Task 4: Resolution / framing check + ordering

**Files:**
- Modify: `src/mini_highlight_advisor/input_check.py`
- Test: `tests/test_input_check.py`

**Interfaces:**
- Consumes: `CheckResult`, `check_input` from earlier tasks.
- Produces:
  - `_check_framing(mask: np.ndarray) -> CheckResult` (id `"resolution"`, label `"Framing"`)
  - Constants `MIN_MASK_AREA = 40_000`, `MIN_COVERAGE = 0.15`
  - Final `check_input` order: `["lighting", "exposure", "focus", "resolution"]`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_input_check.py
def test_tiny_mask_fails_framing_low_coverage():
    rgb = np.full((400, 400, 3), 128, dtype=np.uint8)
    mask = np.zeros((400, 400), dtype=bool)
    mask[0:20, 0:20] = True  # ~0.25% coverage, tiny area
    results = check_input(rgb, mask)
    framing = next(r for r in results if r.id == "resolution")
    assert framing.ok is False
    assert framing.label == "Framing"
    assert "frame" in framing.detail.lower()


def test_well_framed_mask_passes_framing():
    rgb = np.full((400, 400, 3), 128, dtype=np.uint8)
    mask = np.zeros((400, 400), dtype=bool)
    mask[50:350, 100:300] = True  # 60_000 px, 37.5% coverage
    results = check_input(rgb, mask)
    framing = next(r for r in results if r.id == "resolution")
    assert framing.ok is True


def test_check_input_order_is_stable():
    rgb = np.full((400, 400, 3), 128, dtype=np.uint8)
    mask = np.zeros((400, 400), dtype=bool)
    mask[50:350, 100:300] = True
    ids = [r.id for r in check_input(rgb, mask)]
    assert ids == ["lighting", "exposure", "focus", "resolution"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_input_check.py -k "framing or order" -v`
Expected: FAIL — `StopIteration` (no `CheckResult` with id `"resolution"` yet)

- [ ] **Step 3: Write minimal implementation**

Add the constants:

```python
MIN_MASK_AREA = 40_000   # fewer masked px than this => too low-res for clean bands
MIN_COVERAGE = 0.15      # mini fills <15% of the frame => move closer / crop
```

Add the check function (takes only `mask`):

```python
def _check_framing(mask: np.ndarray) -> CheckResult:
    area = int(mask.sum())
    coverage = float(mask.mean())
    ok = area >= MIN_MASK_AREA and coverage >= MIN_COVERAGE
    if ok:
        detail = f"Mini fills {coverage * 100:.0f}% of the frame."
    elif coverage < MIN_COVERAGE:
        detail = (
            f"The mini fills only {coverage * 100:.0f}% of the frame — move closer "
            "or crop so it fills most of the frame."
        )
    else:
        detail = "Photo resolution is low — use a larger image."
    return CheckResult("resolution", "Framing", ok, float(area), detail)
```

Extend `check_input` (note `_check_framing` takes `mask`, not `gray`):

```python
    return [
        _check_lighting(gray, mask),
        _check_exposure(gray, mask),
        _check_focus(gray, mask),
        _check_framing(mask),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_input_check.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/input_check.py tests/test_input_check.py
git commit -m "feat: resolution/framing check + stable check ordering"
```

---

### Task 5: Real-fixture anchor (known-good photo passes all four)

**Files:**
- Test: `tests/test_input_check.py`
- Possibly modify: `src/mini_highlight_advisor/input_check.py` (only if a constant needs tuning so the anchor passes)

**Interfaces:**
- Consumes: `check_input`; `masking.load_image`, `masking.compute_mask`.
- Produces: no new symbols — this task validates the thresholds against a real photo.

**Context:** `fixtures/skaven-hero/primed.png` is the tracked, known-good primed-mini photo (RGBA, so `compute_mask` uses the cheap alpha fast-path — no depth model). It is *defined* as a good input, so it must pass all four checks. If a check fails on it, the corresponding threshold constant is mis-set for real photos — adjust that one constant (and update its comment) until the anchor passes. This is the "sensible defaults, validated against the one real anchor" step.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_input_check.py
from mini_highlight_advisor.masking import load_image, compute_mask

PRIMED_FIXTURE = "fixtures/skaven-hero/primed.png"


def test_known_good_primed_photo_passes_all_checks():
    rgb, alpha = load_image(PRIMED_FIXTURE)
    mask = compute_mask(rgb, alpha)
    results = check_input(rgb, mask)
    failed = [r.id for r in results if not r.ok]
    assert failed == [], f"known-good photo failed checks: {failed}"
    # Every detail is a non-empty, actionable string.
    assert all(isinstance(r.detail, str) and r.detail.strip() for r in results)
```

- [ ] **Step 2: Run test to verify it fails (or passes outright)**

Run: `.venv/Scripts/python -m pytest tests/test_input_check.py::test_known_good_primed_photo_passes_all_checks -v`
Expected: PASS if defaults already suit the real photo. If it FAILS, read which `id`s are in the assertion message, then go to Step 3.

- [ ] **Step 3: Tune only the failing constant (only if Step 2 failed)**

For each failing check, print the measured value and nudge the matching constant so the known-good photo passes while keeping the failure fixtures from Tasks 1–4 still failing. Diagnostic:

```bash
.venv/Scripts/python -c "from mini_highlight_advisor.masking import load_image, compute_mask; from mini_highlight_advisor.input_check import check_input; rgb, a = load_image('fixtures/skaven-hero/primed.png'); m = compute_mask(rgb, a); [print(r.id, round(r.value, 1), r.ok) for r in check_input(rgb, m)]"
```

Adjust the relevant constant (`FLAT_SPREAD_MAX`, `CRUSH_FRAC_MAX`, `BLOWN_FRAC_MAX`, `MIN_MASK_AREA`, `MIN_COVERAGE`, or `MIN_FOCUS_VAR`) and update its comment to reflect the new value's reasoning.

- [ ] **Step 4: Run the full module test to verify everything passes**

Run: `.venv/Scripts/python -m pytest tests/test_input_check.py -v`
Expected: PASS (all synthetic tests AND the anchor). Confirm the Task 1–4 negative tests still fail their checks (they should still be listed as passing tests, since they assert `ok is False`).

- [ ] **Step 5: Commit**

```bash
git add tests/test_input_check.py src/mini_highlight_advisor/input_check.py
git commit -m "test: anchor input checks against known-good primed fixture"
```

---

### Task 6: Shooting guide text + docs page

**Files:**
- Modify: `src/mini_highlight_advisor/input_check.py`
- Create: `docs/photo-guide.md`
- Test: `tests/test_input_check.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `SHOOTING_GUIDE: str` (module-level constant, markdown).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_input_check.py
from mini_highlight_advisor.input_check import SHOOTING_GUIDE


def test_shooting_guide_covers_the_key_points():
    text = SHOOTING_GUIDE.lower()
    for keyword in ["raking", "flash", "frame", "background", "focus"]:
        assert keyword in text, f"shooting guide missing '{keyword}'"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_input_check.py -k shooting_guide -v`
Expected: FAIL — `ImportError: cannot import name 'SHOOTING_GUIDE'`

- [ ] **Step 3: Write minimal implementation**

Add to `input_check.py`:

```python
SHOOTING_GUIDE = """\
### How to photograph your mini

- **Raking side light.** Light the mini from one side at roughly 45° so the sculpt
  casts soft shadows — that shading is exactly what the tool reads.
- **No on-axis / built-in flash.** A flash pointing straight at the mini flattens the
  form and erases the shading signal.
- **Fill the frame.** Get close (or crop) so the mini occupies most of the photo.
- **Plain, neutral background.** A clean backdrop helps isolate the mini.
- **Sharp focus, steady hands.** Focus on the mini and use a timer or brace your hands
  to avoid blur.
- **A zenithal-primed (grey/white) mini reads best** — it is already a shading map.
"""
```

Create `docs/photo-guide.md` with the same content (drop the leading `### ` heading line and use a top-level `# How to photograph your mini` instead):

```markdown
# How to photograph your mini

- **Raking side light.** Light the mini from one side at roughly 45° so the sculpt
  casts soft shadows — that shading is exactly what the tool reads.
- **No on-axis / built-in flash.** A flash pointing straight at the mini flattens the
  form and erases the shading signal.
- **Fill the frame.** Get close (or crop) so the mini occupies most of the photo.
- **Plain, neutral background.** A clean backdrop helps isolate the mini.
- **Sharp focus, steady hands.** Focus on the mini and use a timer or brace your hands
  to avoid blur.
- **A zenithal-primed (grey/white) mini reads best** — it is already a shading map.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_input_check.py -k shooting_guide -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/input_check.py docs/photo-guide.md tests/test_input_check.py
git commit -m "feat: shooting guide text + docs/photo-guide.md"
```

---

### Task 7: Wire the quality panel into app.py

**Files:**
- Modify: `app.py` (Miniature tab, after the image loads and the mask is computed, before the highlight results render)
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: `check_input`, `SHOOTING_GUIDE`, `CheckResult` from `input_check`; the mask already computed in `app.py`.
- Produces: no new importable symbols — UI wiring only.

**Context:** Read `app.py` first to find where the mini image is loaded and where `compute_mask` (or the analysis path) already produces the mask. Reuse that exact mask — do **not** call `compute_mask` a second time (it may run the depth model). Render the panel above the highlight results.

- [ ] **Step 1: Add a smoke assertion (module-level integration)**

```python
# add to tests/test_smoke.py
def test_input_check_panel_inputs_are_available():
    # The app renders one row per check + a guide; assert the contract it relies on.
    import numpy as np
    from mini_highlight_advisor.input_check import check_input, SHOOTING_GUIDE
    rgb = np.full((400, 400, 3), 128, dtype=np.uint8)
    mask = np.zeros((400, 400), dtype=bool)
    mask[50:350, 100:300] = True
    results = check_input(rgb, mask)
    assert [r.id for r in results] == ["lighting", "exposure", "focus", "resolution"]
    assert all(hasattr(r, "ok") and r.detail for r in results)
    assert SHOOTING_GUIDE.strip()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_smoke.py -k input_check_panel -v`
Expected: PASS (this contract is already satisfied by Tasks 1–6; it guards against regressions before the UI wiring).

- [ ] **Step 3: Wire the panel into `app.py`**

In the Miniature tab, immediately after the mask is available and before the highlight
results, add (adapt variable names to the existing `app.py`):

```python
import streamlit as st
from mini_highlight_advisor.input_check import check_input, SHOOTING_GUIDE

# `rgb` and `mask` are the already-loaded image and already-computed mask.
st.subheader("\U0001F4F7 Photo quality")
for r in check_input(rgb, mask):
    line = f"**{r.label}** — {r.detail}"
    if r.ok:
        st.success(line)
    else:
        st.warning(line)
with st.expander("How to photograph your mini"):
    st.markdown(SHOOTING_GUIDE)
```

- [ ] **Step 4: Manually verify in the app**

Run: `streamlit run app.py`, upload `fixtures/skaven-hero/primed.png`, and confirm: the "Photo quality" panel appears above the highlight plan, all four rows show green with their confirmation text, the expander shows the guide, and the highlight plan still renders normally (non-blocking). Then run the full suite:

Run: `.venv/Scripts/python -m pytest`
Expected: PASS (whole suite green).

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_smoke.py
git commit -m "feat: render non-blocking photo-quality panel + guide in app"
```

---

## Self-Review Notes

- **Spec coverage:** lighting/exposure/focus/resolution checks → Tasks 1–4; always-on panel with actionable details → check functions (every `detail` actionable) + Task 7 rendering; shooting guide + `docs/photo-guide.md` → Task 6; raw-grey-not-luminance_light → `_to_gray` (Task 1); reuse-computed-mask → Task 7 context note; non-blocking → Task 7 (panel renders above, never gates); named tunable constants → each check task; known-good anchor → Task 5; synthetic per-failure-mode tests → Tasks 1–4.
- **Deferred items (spec "Out of scope")** intentionally have no task: empirical multi-shot calibration, per-region checks, auto-fixing pixels, blocking behaviour.
- **Type consistency:** `CheckResult(id, label, ok, value, detail)` used identically across all tasks; `check_input(rgb, mask) -> list[CheckResult]`; `_check_framing` takes `mask` only (the one check that ignores `gray`) — called out in Task 4.
