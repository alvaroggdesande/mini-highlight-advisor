# Per-band coverage sliders + 7-layer cap — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user set each layer's coverage percentage with a live-redrawing image, and raise the layer cap from 5 to 7.

**Architecture:** Split the pipeline so expensive mask+luminance runs once per image (`prepare_shading`) while banding+rendering re-runs on every coverage tweak (`band_and_render`). The coverage UI uses a "remainder band" model: `n-1` exact-% sliders plus a lightest band that auto-absorbs the rest, with each slider's live `max_value` guaranteeing the total never exceeds 100%.

**Tech Stack:** Python 3.11, NumPy, OpenCV, Streamlit, pytest. UI-agnostic core in `src/mini_highlight_advisor/`, Streamlit UI in `app.py`.

## Global Constraints

- Coverage lists handed to `band_light` are **fractions summing to 1.0** (not percents) — they are cumulative quantile cut-points; a wrong total corrupts the top band.
- Default layer count stays **5**; **7** is the new ceiling, not the new default.
- Remainder band `floor = 3.0` (percent) reserved so the lightest band is always `>= floor`.
- Recipes store palette + roles only — **no coverage** persisted.
- Whole-mini only (v1). No per-region coverage.
- Core stays UI-agnostic: no Streamlit imports in `src/`.
- Tests: `.venv/Scripts/python -m pytest`. Use the alpha fast-path (full-model `alpha`) in tests to avoid the depth model.

---

### Task 1: Split pipeline into `prepare_shading` + `band_and_render`

**Files:**
- Modify: `src/mini_highlight_advisor/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `compute_mask`, `luminance_light`, `band_light`, `coverage_pct`, `default_coverage`, `role_names`, `paint_preview`, `render_legend`, `compose_panel`, `per_band_images` (all existing, unchanged).
- Produces:
  - `ShadingResult` dataclass with fields `mask: np.ndarray`, `light: np.ndarray`.
  - `prepare_shading(rgb: np.ndarray, alpha: np.ndarray | None) -> ShadingResult`
  - `band_and_render(rgb: np.ndarray, mask: np.ndarray, light: np.ndarray, palette: list[PaintColor], coverage: list[float]) -> HighlightResult` — `coverage` is a fraction list summing to 1.0, length `len(palette)`.
  - `analyze(rgb, alpha, palette, coverage: list[float] | None = None) -> HighlightResult` — unchanged behaviour when `coverage is None`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline.py`:

```python
def test_prepare_then_band_matches_analyze_default():
    from mini_highlight_advisor.palette import PaintColor, default_coverage
    from mini_highlight_advisor.pipeline import prepare_shading, band_and_render

    rgb = np.random.default_rng(0).integers(0, 255, (32, 32, 3), dtype=np.uint8)
    alpha = np.full((32, 32), 255, dtype=np.uint8)  # full-model alpha, fast path
    palette = [PaintColor("A", "#202020"), PaintColor("B", "#808080"), PaintColor("C", "#f0f0f0")]

    baseline = analyze(rgb, alpha, palette)  # coverage=None -> default

    sh = prepare_shading(rgb, alpha)
    split = band_and_render(rgb, sh.mask, sh.light, palette, default_coverage(len(palette)))

    assert np.array_equal(split.bands, baseline.bands)
    assert split.coverage == baseline.coverage
    assert split.roles == baseline.roles


def test_analyze_accepts_custom_coverage():
    from mini_highlight_advisor.palette import PaintColor

    rgb = np.random.default_rng(1).integers(0, 255, (40, 40, 3), dtype=np.uint8)
    alpha = np.full((40, 40), 255, dtype=np.uint8)
    palette = [PaintColor("A", "#202020"), PaintColor("B", "#808080"), PaintColor("C", "#f0f0f0")]

    # Fatten the shadow band; expect its coverage to dominate.
    result = analyze(rgb, alpha, palette, coverage=[0.6, 0.3, 0.1])
    assert result.coverage[0] > result.coverage[-1]
    assert abs(sum(result.coverage) - 100.0) < 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline.py::test_prepare_then_band_matches_analyze_default tests/test_pipeline.py::test_analyze_accepts_custom_coverage -v`
Expected: FAIL — `cannot import name 'prepare_shading'` / `analyze() got an unexpected keyword argument 'coverage'`.

- [ ] **Step 3: Refactor `pipeline.py`**

Replace the body of `pipeline.py` (keep imports; add `ShadingResult`) with:

```python
@dataclass
class ShadingResult:
    mask: np.ndarray
    light: np.ndarray


def prepare_shading(rgb: np.ndarray, alpha: np.ndarray | None) -> ShadingResult:
    mask = compute_mask(rgb, alpha)
    light = luminance_light(rgb, mask)
    return ShadingResult(mask, light)


def band_and_render(
    rgb: np.ndarray,
    mask: np.ndarray,
    light: np.ndarray,
    palette: list[PaintColor],
    coverage: list[float],
) -> HighlightResult:
    n = len(palette)
    colors = [p.rgb for p in palette]
    names = [p.name for p in palette]
    roles = role_names(n)

    bands = band_light(light, mask, coverage)
    cov = coverage_pct(bands, mask, n)

    preview_rgb = paint_preview(rgb, bands, mask, colors)
    legend = render_legend(colors, names, roles, cov, height=preview_rgb.shape[0])
    panel = compose_panel(rgb, preview_rgb, legend)
    steps = per_band_images(rgb, bands, mask, colors)

    return HighlightResult(mask, light, bands, cov, roles, preview_rgb, panel, steps)


def analyze(
    rgb: np.ndarray,
    alpha: np.ndarray | None,
    palette: list[PaintColor],
    coverage: list[float] | None = None,
) -> HighlightResult:
    if coverage is None:
        coverage = default_coverage(len(palette))
    shading = prepare_shading(rgb, alpha)
    return band_and_render(rgb, shading.mask, shading.light, palette, coverage)
```

- [ ] **Step 4: Run the full pipeline test file to verify pass + no regression**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline.py -v`
Expected: PASS (new tests + the three pre-existing `analyze` tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/pipeline.py tests/test_pipeline.py
git commit -m "refactor: split pipeline into prepare_shading + band_and_render; optional coverage"
```

---

### Task 2: Role names for 6/7 layers + interpolated-grey ramp helper

**Files:**
- Modify: `src/mini_highlight_advisor/palette.py`
- Test: `tests/test_palette.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `_ROLES` extended with keys `6` and `7`.
  - `ramp_hex(i: int, n: int) -> str` — hex of an evenly-spaced neutral grey; `i=0` -> near-black, `i=n-1` -> `#ffffff`; brightness strictly increases with `i`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_palette.py`:

```python
def test_role_names_six_and_seven():
    from mini_highlight_advisor.palette import role_names
    assert role_names(6) == [
        "Shadow", "Deep Base", "Base", "Midtone", "Highlight", "Edge Highlight"
    ]
    assert role_names(7) == [
        "Shadow", "Deep Base", "Base", "Midtone", "Upper Midtone",
        "Highlight", "Edge Highlight",
    ]


def test_ramp_hex_endpoints_and_monotonic():
    from mini_highlight_advisor.palette import PaintColor, ramp_hex
    n = 7
    lums = [PaintColor("x", ramp_hex(i, n)).rgb.mean() for i in range(n)]
    assert lums[0] < 40          # near-black low end
    assert ramp_hex(n - 1, n) == "#ffffff"
    assert lums == sorted(lums)  # strictly non-decreasing, dark to light
    assert lums[-1] > lums[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_palette.py::test_role_names_six_and_seven tests/test_palette.py::test_ramp_hex_endpoints_and_monotonic -v`
Expected: FAIL — `role_names(6)` returns generic `["Layer 1", ...]`; `cannot import name 'ramp_hex'`.

- [ ] **Step 3: Extend `_ROLES` and add `ramp_hex`**

In `palette.py`, extend the `_ROLES` dict:

```python
_ROLES = {
    3: ["Shadow", "Base", "Highlight"],
    4: ["Shadow", "Base", "Midtone", "Highlight"],
    5: ["Shadow", "Base", "Midtone", "Highlight", "Edge Highlight"],
    6: ["Shadow", "Deep Base", "Base", "Midtone", "Highlight", "Edge Highlight"],
    7: ["Shadow", "Deep Base", "Base", "Midtone", "Upper Midtone",
        "Highlight", "Edge Highlight"],
}
```

Add near `default_coverage`:

```python
def ramp_hex(i: int, n: int) -> str:
    # Evenly-spaced neutral grey on the black->white ramp for an n-layer palette.
    v = 0 if n <= 1 else round(255 * i / (n - 1))
    return f"#{v:02x}{v:02x}{v:02x}"
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_palette.py -v`
Expected: PASS (new tests + existing palette tests unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/palette.py tests/test_palette.py
git commit -m "feat: role names for 6/7 layers + interpolated-grey ramp_hex helper"
```

---

### Task 3: Coverage-slider math helpers (remainder + live max)

**Files:**
- Modify: `src/mini_highlight_advisor/palette.py`
- Test: `tests/test_palette.py`

**Interfaces:**
- Consumes: nothing.
- Produces (pure functions, percent domain 0–100, UI-agnostic so they are unit-testable without Streamlit):
  - `remainder_pct(others: list[float]) -> float` — `max(0.0, 100.0 - sum(others))`.
  - `slider_max_pct(others: list[float], floor: float = 3.0) -> float` — `max(0.0, 100.0 - sum(others) - floor)`; `others` are the OTHER sliders' current values (excluding the one being drawn).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_palette.py`:

```python
def test_remainder_pct_fills_to_100():
    from mini_highlight_advisor.palette import remainder_pct
    assert remainder_pct([40.0, 30.0, 20.0]) == 10.0
    assert remainder_pct([]) == 100.0
    assert remainder_pct([60.0, 60.0]) == 0.0  # clamped, never negative


def test_slider_max_pct_reserves_floor():
    from mini_highlight_advisor.palette import slider_max_pct
    # Two other sliders at 30 each -> 100-60-3 = 37 headroom for this slider.
    assert slider_max_pct([30.0, 30.0], floor=3.0) == 37.0
    # Never negative even when others already over budget.
    assert slider_max_pct([98.0, 10.0], floor=3.0) == 0.0


def test_slider_max_invariant_keeps_total_under_100():
    # If each slider stays within its live max, the n-1 sliders + floor <= 100.
    from mini_highlight_advisor.palette import slider_max_pct, remainder_pct
    sliders = [0.0, 0.0, 0.0]  # n-1 = 3 controllable bands
    # Simulate pushing slider 0 to its max, then slider 1, then slider 2.
    for i in range(len(sliders)):
        others = [v for j, v in enumerate(sliders) if j != i]
        sliders[i] = slider_max_pct(others, floor=3.0)
    assert sum(sliders) <= 97.0 + 1e-9
    assert remainder_pct(sliders) >= 3.0 - 1e-9
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_palette.py -k "remainder_pct or slider_max" -v`
Expected: FAIL — `cannot import name 'remainder_pct'` / `slider_max_pct`.

- [ ] **Step 3: Add the helpers**

In `palette.py`, after `ramp_hex`:

```python
def remainder_pct(others: list[float]) -> float:
    # The lightest band absorbs whatever the other sliders leave.
    return max(0.0, 100.0 - sum(others))


def slider_max_pct(others: list[float], floor: float = 3.0) -> float:
    # Live upper bound for one slider so the remainder band keeps at least `floor`.
    return max(0.0, 100.0 - sum(others) - floor)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_palette.py -k "remainder_pct or slider_max" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/palette.py tests/test_palette.py
git commit -m "feat: coverage-slider math helpers (remainder + live slider max)"
```

---

### Task 4: Wire coverage sliders, 7-layer cap, and live redraw into the app

**Files:**
- Modify: `app.py`

**Interfaces:**
- Consumes: `prepare_shading`, `band_and_render` (Task 1); `role_names`, `ramp_hex`, `remainder_pct`, `slider_max_pct`, `default_coverage` (Tasks 2–3).
- Produces: no new public API — Streamlit UI only. No automated test (Streamlit UI); verified manually per repo convention.

- [ ] **Step 1: Raise the layer-count slider ceiling to 7**

In `app.py`, change:

```python
n = st.slider("Number of layers", 3, 5, key="n")
```
to:
```python
n = st.slider("Number of layers", 3, 7, key="n")
```
Leave `st.session_state.setdefault("n", 5)` above it unchanged (default stays 5).

- [ ] **Step 2: Seed palette slots 6/7 with interpolated greys**

In the palette-slot loop, replace the default lookup:

```python
default = DEFAULT_PALETTE[min(i, len(DEFAULT_PALETTE) - 1)]
```
with:
```python
if i < len(DEFAULT_PALETTE):
    default = DEFAULT_PALETTE[i]
else:
    default = PaintColor(f"Grey {i + 1}", ramp_hex(i, n))
```
Add `ramp_hex` to the palette import at the top of `app.py`:
```python
from mini_highlight_advisor.palette import DEFAULT_PALETTE, PaintColor, role_names, ramp_hex
```
Note: `ramp_hex(i, n)` has no curated `code`, so its slot seeds as `CUSTOM` via the existing `find_by_code(...) is None` branch — no extra handling needed.

- [ ] **Step 3: Add the coverage-sliders block**

After the palette-slot loop (before "Save as recipe"), add a coverage section. It seeds from `default_coverage(n)` (as percents), reseeds when `n` changes, offers a reset button, and displays the auto remainder band. Uses `role_names(n)` for labels.

```python
    # --- Coverage per layer (remainder model) ---
    st.markdown("**Coverage** (% of the model each layer occupies)")
    roles_now = role_names(n)
    cov_floor = 3.0
    seed = [round(f * 100, 1) for f in default_coverage(n)]

    # Reseed slider state whenever the layer count changes.
    if st.session_state.get("cov_n") != n:
        for i in range(n - 1):
            st.session_state[f"cov_pct_{i}"] = seed[i]
        st.session_state["cov_n"] = n

    if st.button("Reset to default curve"):
        for i in range(n - 1):
            st.session_state[f"cov_pct_{i}"] = seed[i]
        st.rerun()

    cov_pcts: list[float] = []
    for i in range(n - 1):
        others = [st.session_state.get(f"cov_pct_{j}", seed[j])
                  for j in range(n - 1) if j != i]
        smax = slider_max_pct(others, floor=cov_floor)
        st.session_state.setdefault(f"cov_pct_{i}", seed[i])
        # Keep any stale seeded value within the current live max.
        if st.session_state[f"cov_pct_{i}"] > smax:
            st.session_state[f"cov_pct_{i}"] = smax
        val = st.slider(
            f"{roles_now[i]}", 0.0, max(smax, 0.1), step=0.5, key=f"cov_pct_{i}",
        )
        cov_pcts.append(val)

    remainder = remainder_pct(cov_pcts)
    st.caption(f"**{roles_now[-1]} · auto: {remainder:.1f}%**  (remainder — always keeps ≥ {cov_floor:.0f}%)")

    coverage = [p / 100.0 for p in (cov_pcts + [remainder])]  # fractions, sum == 1.0
```

Add the helpers to the import line:
```python
from mini_highlight_advisor.palette import (
    DEFAULT_PALETTE, PaintColor, role_names, ramp_hex,
    default_coverage, remainder_pct, slider_max_pct,
)
```

- [ ] **Step 4: Cache shading and redraw with the live coverage**

Reuse the existing temp-file + `load_image` path inside a cached function so no new core loader is needed. Caching keys on the uploaded bytes + suffix, so the depth model runs once per image. Add near the top of `app.py` (module level, after imports):

```python
@st.cache_data(show_spinner=False)
def _shading(image_bytes: bytes, suffix: str):
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name
    try:
        rgb, alpha = load_image(tmp_path)
    finally:
        os.unlink(tmp_path)
    return rgb, alpha, prepare_shading(rgb, alpha)
```

Replace the upload block's temp-file/analyze section. Current code (`app.py:157-164`):

```python
suffix = os.path.splitext(uploaded.name)[1]
with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
    tmp.write(uploaded.getbuffer())
    tmp_path = tmp.name
try:
    with st.spinner("Analyzing (first run downloads the depth model if no alpha channel)..."):
        rgb, alpha = load_image(tmp_path)
        result = analyze(rgb, alpha, palette)
```
becomes:
```python
suffix = os.path.splitext(uploaded.name)[1]
try:
    with st.spinner("Preparing shading (first run downloads the depth model if no alpha channel)..."):
        rgb, alpha, shading = _shading(uploaded.getvalue(), suffix)
    result = band_and_render(rgb, shading.mask, shading.light, palette, coverage)
```
Delete the now-orphaned `tmp_path` cleanup in the `finally:` at the end of this `try` block (the cached function owns temp-file lifecycle now). Verify the trailing `finally: os.unlink(tmp_path)` / `os.remove(tmp_path)` is removed so no `NameError` on the missing `tmp_path`.

Update imports:
```python
from mini_highlight_advisor.pipeline import prepare_shading, band_and_render
```
(remove the now-unused `analyze` import). Keep the existing `import os`, `import tempfile`, and `from mini_highlight_advisor.masking import load_image` — all still used.

- [ ] **Step 5: Manual verification (run the app)**

Run: `streamlit run app.py`

Confirm:
1. Layer slider goes to 7; picking 6 or 7 shows roles `… Upper Midtone, Highlight, Edge Highlight` and slots 6/7 seed as distinct greys (not two Dead Whites).
2. Coverage shows `n-1` sliders + an `auto: Y%` remainder line; sliders reflect the default curve on first load.
3. Dragging a slider up shrinks the auto remainder; you cannot push the controllable sliders past a total that would drop the remainder below 3%.
4. The painted image + layer guide redraw on each slider change, and re-uploading the same image does not re-run the depth model (shading is cached).
5. "Reset to default curve" restores the seeded percentages.
6. Changing the layer count reseeds the sliders (no stale curve from the previous count).

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: per-band coverage sliders + 7-layer cap with live redraw"
```

---

## Self-Review

**Spec coverage:**
- Remainder-band coverage UI → Task 4 Step 3 (+ helpers in Task 3). ✓
- Never-exceeds invariant → `slider_max_pct` (Task 3) + live recompute per slider (Task 4 Step 3). ✓
- Seed from `default_coverage`, reset button, reseed on `n` change → Task 4 Step 3. ✓
- Live redraw via `prepare_shading` (cached) + `band_and_render` → Tasks 1 + 4 Steps 4/4a. ✓
- `analyze` wrapper + optional coverage → Task 1. ✓
- Cap → 7, role names 6/7, interpolated greys for slots 6/7 → Tasks 2 + 4 Steps 1/2. ✓
- Default stays 5 → Task 4 Step 1 (unchanged `setdefault`). ✓
- Recipes unchanged (no coverage) → not touched; Save-recipe block left as-is. ✓

**Placeholder scan:** No TBD/TODO; every code step has concrete code. Task 4a is a conditional ("if not present") with a precise instruction, not a placeholder.

**Type consistency:** `ShadingResult(mask, light)`, `prepare_shading -> ShadingResult`, `band_and_render(rgb, mask, light, palette, coverage) -> HighlightResult`, `coverage` fraction-list summing to 1.0 — consistent across Tasks 1 and 4. `remainder_pct`/`slider_max_pct` operate in percent; the app converts to fractions once, at the end of Step 3. `ramp_hex(i, n)` signature consistent Tasks 2 + 4.
