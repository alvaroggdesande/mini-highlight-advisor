# Region UX v3 + Palette Ergonomics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Four small region/palette-editor ergonomics — rename a region, union multiple lassos into one region, show/paste hex per palette slot, and blend an interior slot from its neighbours.

**Architecture:** Three new pure helpers (`regions.polygons_to_mask`, `palette.valid_hex`, and Lab-blend helpers in `color.py`) plus one `RegionBook.set_name_at` method, each unit-tested; then four localized wiring changes in the Streamlit `app.py` editor, verified manually. No change to the banding/lighting/edge render engine.

**Tech Stack:** Python 3.11, Streamlit 1.61, numpy, Pillow, OpenCV, streamlit-drawable-canvas. Tests via `.venv/Scripts/python -m pytest`.

## Global Constraints

- Primed / monochrome minis only — this batch does not touch the shading engine.
- "Whole mini" is region index 0 and is never renamable or removable.
- Region outlines remain immutable once drawn (no reshape); union happens only at Add-region time.
- Follow existing patterns: pure colour math lives in `color.py`; the Streamlit widget-key rehydration pattern in `app.py:287-303` (`setdefault` from the book) must not be broken.
- Hex format is `#rrggbb` lower-case; paste accepts `#rgb`/`#rrggbb` any case and normalises.
- Never build on `main`; work stays on `feat/region-ux-v3-palette-ergonomics`. Commit per task.
- Spec file placement note: the spec named `blend_hex_lab`/`valid_hex` under `palette.py`. Implementation puts the Lab colour math (`lab_to_rgb`, `rgb_to_hex`, `blend_hex_lab`) in `color.py` (where `rgb_to_lab`/`linear_blend` already live) and keeps `valid_hex` in `palette.py`. Intent preserved.

---

### Task 1: `polygons_to_mask` — union of multiple lassos

**Files:**
- Modify: `src/mini_highlight_advisor/regions.py`
- Test: `tests/test_regions.py`

**Interfaces:**
- Consumes: existing `polygon_to_mask(points, shape) -> np.ndarray` in the same module.
- Produces: `polygons_to_mask(point_lists: list, shape: tuple[int, int]) -> np.ndarray` — boolean OR of `polygon_to_mask` over each list; empty input returns an all-False mask of `shape`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_regions.py`:

```python
def test_polygons_to_mask_unions_disjoint_shapes():
    from mini_highlight_advisor.regions import polygons_to_mask
    a = [(0, 0), (0, 2), (2, 2), (2, 0)]      # top-left block
    b = [(5, 5), (5, 7), (7, 7), (7, 5)]      # bottom-right block
    m = polygons_to_mask([a, b], (8, 8))
    assert m.dtype == bool and m.shape == (8, 8)
    assert m[1, 1] and m[6, 6]                # both filled
    assert not m[1, 6]                        # gap between them stays empty


def test_polygons_to_mask_single_matches_polygon_to_mask():
    from mini_highlight_advisor.regions import polygons_to_mask, polygon_to_mask
    sq = [(1, 1), (1, 4), (4, 4), (4, 1)]
    assert np.array_equal(polygons_to_mask([sq], (6, 6)), polygon_to_mask(sq, (6, 6)))


def test_polygons_to_mask_empty_is_all_false():
    from mini_highlight_advisor.regions import polygons_to_mask
    m = polygons_to_mask([], (4, 4))
    assert m.shape == (4, 4) and not m.any()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_regions.py -k polygons_to_mask -v`
Expected: FAIL with `ImportError`/`cannot import name 'polygons_to_mask'`.

- [ ] **Step 3: Implement `polygons_to_mask`**

Append to `src/mini_highlight_advisor/regions.py`:

```python
def polygons_to_mask(point_lists, shape) -> np.ndarray:
    """Union of several polygon rings into one boolean mask (shape = (h, w))."""
    out = np.zeros(shape, dtype=bool)
    for pts in point_lists:
        out |= polygon_to_mask(pts, shape)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_regions.py -k polygons_to_mask -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/regions.py tests/test_regions.py
git commit -m "feat: polygons_to_mask — union multiple lassos into one region mask"
```

---

### Task 2: `RegionBook.set_name_at` — rename a drawn region

**Files:**
- Modify: `src/mini_highlight_advisor/region_state.py`
- Test: `tests/test_region_state.py`

**Interfaces:**
- Consumes: existing `RegionBook` (`drawn[g-1].name`, `_check`).
- Produces: `RegionBook.set_name_at(self, g: int, name: str) -> None` — sets `drawn[g-1].name`; raises `ValueError` if `g == 0` (Whole mini fixed); a blank/whitespace name is rejected (keeps the old name, no error).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_region_state.py`:

```python
def test_set_name_at_renames_drawn_region():
    b = new_book(3)
    b.add(_mask(), "Cloak", default_ramp(3), default_coverage(3))
    b.set_name_at(1, "Robe")
    assert b.names() == ["Whole mini", "Robe"]

def test_set_name_at_rejects_blank_keeps_old():
    b = new_book(3)
    b.add(_mask(), "Cloak", default_ramp(3), default_coverage(3))
    b.set_name_at(1, "   ")
    assert b.names() == ["Whole mini", "Cloak"]

def test_set_name_at_cannot_rename_whole_mini():
    b = new_book(3)
    try:
        b.set_name_at(0, "Nope")
        assert False, "expected ValueError"
    except ValueError:
        pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_region_state.py -k set_name_at -v`
Expected: FAIL with `AttributeError: 'RegionBook' object has no attribute 'set_name_at'`.

- [ ] **Step 3: Implement `set_name_at`**

Add this method to `RegionBook` in `src/mini_highlight_advisor/region_state.py` (e.g. after `set_coverage_at`):

```python
    def set_name_at(self, g: int, name: str) -> None:
        if g == 0:
            raise ValueError("cannot rename the 'Whole mini' region")
        self._check(g)
        clean = name.strip()
        if clean:
            self.drawn[g - 1].name = clean
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_region_state.py -k set_name_at -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/region_state.py tests/test_region_state.py
git commit -m "feat: RegionBook.set_name_at — rename a drawn region in place"
```

---

### Task 3: `palette.valid_hex` — validate/normalise a pasted hex

**Files:**
- Modify: `src/mini_highlight_advisor/palette.py`
- Test: `tests/test_palette.py`

**Interfaces:**
- Produces: `palette.valid_hex(s: str) -> str | None` — returns a normalised `#rrggbb` (lower-case) for a valid `#rgb`/`#rrggbb` (any case, leading `#` optional); returns `None` for anything else.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_palette.py`:

```python
def test_valid_hex_accepts_and_normalises():
    from mini_highlight_advisor.palette import valid_hex
    assert valid_hex("#AABBCC") == "#aabbcc"
    assert valid_hex("aabbcc") == "#aabbcc"      # leading # optional
    assert valid_hex("#abc") == "#aabbcc"        # short form expands

def test_valid_hex_rejects_bad_input():
    from mini_highlight_advisor.palette import valid_hex
    assert valid_hex("xyz") is None
    assert valid_hex("#12") is None
    assert valid_hex("#12345") is None
    assert valid_hex("") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_palette.py -k valid_hex -v`
Expected: FAIL with `ImportError: cannot import name 'valid_hex'`.

- [ ] **Step 3: Implement `valid_hex`**

Add to `src/mini_highlight_advisor/palette.py` (near `ramp_hex`):

```python
def valid_hex(s: str) -> str | None:
    """Normalise a user-typed hex to '#rrggbb' lower-case, or None if invalid.
    Accepts '#rgb'/'#rrggbb' with any case and an optional leading '#'."""
    if not s:
        return None
    h = s.strip().lstrip("#").lower()
    if len(h) == 3 and all(c in "0123456789abcdef" for c in h):
        h = "".join(c * 2 for c in h)
    if len(h) == 6 and all(c in "0123456789abcdef" for c in h):
        return f"#{h}"
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_palette.py -k valid_hex -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/palette.py tests/test_palette.py
git commit -m "feat: palette.valid_hex — validate/normalise a pasted hex"
```

---

### Task 4: Lab blend helpers — `lab_to_rgb`, `rgb_to_hex`, `blend_hex_lab`

**Files:**
- Modify: `src/mini_highlight_advisor/color.py`
- Test: `tests/test_color.py`

**Interfaces:**
- Consumes: existing `color.py` internals — `rgb_to_lab`, `lab_of_hex`, `hex_to_rgb`, `_linear_to_srgb255`, and the constants `xn, yn, zn` used in `rgb_to_lab` (0.95047, 1.0, 1.08883).
- Produces:
  - `lab_to_rgb(lab) -> tuple[float, float, float]` — inverse of `rgb_to_lab`, returns 0–255 sRGB floats.
  - `rgb_to_hex(rgb) -> str` — clamps/rounds 0–255 channels to `#rrggbb`.
  - `blend_hex_lab(h1: str, h2: str) -> str` — Lab-midpoint of two hexes as `#rrggbb`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_color.py`:

```python
def test_rgb_to_hex_clamps_and_formats():
    from mini_highlight_advisor.color import rgb_to_hex
    assert rgb_to_hex((0, 0, 0)) == "#000000"
    assert rgb_to_hex((255, 255, 255)) == "#ffffff"
    assert rgb_to_hex((300, -5, 128)) == "#ff0080"      # clamp out-of-range

def test_lab_roundtrip_is_near_identity():
    from mini_highlight_advisor.color import hex_to_rgb, rgb_to_lab, lab_to_rgb
    for hexv in ("#000000", "#ffffff", "#6d7173", "#7a1f22", "#3f6db0"):
        r0, g0, b0 = hex_to_rgb(hexv)
        r1, g1, b1 = lab_to_rgb(rgb_to_lab((r0, g0, b0)))
        assert abs(r1 - r0) < 2 and abs(g1 - g0) < 2 and abs(b1 - b0) < 2

def test_blend_hex_lab_black_white_is_mid_grey():
    from mini_highlight_advisor.color import blend_hex_lab
    out = blend_hex_lab("#000000", "#ffffff")
    r = int(out[1:3], 16)
    assert out[1:3] == out[3:5] == out[5:7]     # neutral grey
    assert 108 <= r <= 128                       # perceptual mid (L~50), not linear-bright

def test_blend_hex_lab_symmetric_and_endpoints():
    from mini_highlight_advisor.color import blend_hex_lab
    assert blend_hex_lab("#123456", "#abcdef") == blend_hex_lab("#abcdef", "#123456")
    same = blend_hex_lab("#4488cc", "#4488cc")
    r, g, b = int(same[1:3], 16), int(same[3:5], 16), int(same[5:7], 16)
    assert abs(r - 0x44) <= 1 and abs(g - 0x88) <= 1 and abs(b - 0xcc) <= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_color.py -k "rgb_to_hex or lab_roundtrip or blend_hex_lab" -v`
Expected: FAIL with `ImportError` on `lab_to_rgb`/`rgb_to_hex`/`blend_hex_lab`.

- [ ] **Step 3: Implement the three helpers**

Append to `src/mini_highlight_advisor/color.py`:

```python
def lab_to_rgb(lab) -> tuple[float, float, float]:
    """Inverse of rgb_to_lab: CIE-Lab (D65) -> sRGB 0-255 floats."""
    L, a, b = lab
    fy = (L + 16) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0

    def finv(t: float) -> float:
        return t ** 3 if t ** 3 > 0.008856 else (t - 16 / 116) / 7.787

    xn, yn, zn = 0.95047, 1.0, 1.08883
    x, y, z = xn * finv(fx), yn * finv(fy), zn * finv(fz)
    r = x * 3.2406 + y * -1.5372 + z * -0.4986
    g = x * -0.9689 + y * 1.8758 + z * 0.0415
    bl = x * 0.0557 + y * -0.2040 + z * 1.0570
    return (_linear_to_srgb255(r), _linear_to_srgb255(g), _linear_to_srgb255(bl))


def rgb_to_hex(rgb) -> str:
    """Clamp/round an sRGB 0-255 triple to '#rrggbb'."""
    r, g, b = (max(0, min(255, int(round(v)))) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def blend_hex_lab(h1: str, h2: str) -> str:
    """Perceptual midpoint of two hex colours, blended in CIE-Lab."""
    l1 = lab_of_hex(h1)
    l2 = lab_of_hex(h2)
    mid = tuple((a + b) / 2.0 for a, b in zip(l1, l2))
    return rgb_to_hex(lab_to_rgb(mid))
```

Note: `_linear_to_srgb255` already clamps its input to [0,1] before gamma-encoding, so out-of-gamut Lab midpoints stay in range.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_color.py -k "rgb_to_hex or lab_roundtrip or blend_hex_lab" -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/color.py tests/test_color.py
git commit -m "feat: color Lab inverse + blend_hex_lab for perceptual midpoint"
```

---

### Task 5: Wire rename into the editor panel (`app.py`)

**Files:**
- Modify: `app.py` (editor panel, just after the `### Editing: <name>` heading at `app.py:285`)

**Interfaces:**
- Consumes: `RegionBook.set_name_at` (Task 2); `book`, `sel` already in scope.

UI-only task — verified manually (no unit test; the region editor is a Streamlit surface).

- [ ] **Step 1: Add the rename field**

Immediately after the `st.markdown(f"### Editing: **{book.names()[sel]}**")` line (`app.py:285`), insert:

```python
        # Rename the selected drawn region (Whole mini / index 0 is fixed).
        if sel >= 1:
            renamed = st.text_input("Region name", value=book.names()[sel], key=f"rename_{sel}")
            if renamed.strip() and renamed.strip() != book.names()[sel]:
                book.set_name_at(sel, renamed)
                st.session_state.pop("_loaded_g", None)
                st.rerun()
```

- [ ] **Step 2: Manual verification**

Run: `.venv/Scripts/python -m streamlit run app.py`
Then: upload a mini → draw a region → in the editor, change "Region name" to `Robe` → press Enter.
Expected: the `### Editing:` heading and the right-hand region radio both now read `Robe`; no redraw needed. Selecting "Whole mini" shows **no** rename field.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: rename a selected region in the editor panel"
```

---

### Task 6: Union all lassos on Add region (`app.py`)

**Files:**
- Modify: `app.py` (Add-region handler, `app.py:258-274`)

**Interfaces:**
- Consumes: `regions.polygons_to_mask` (Task 1); `_points_from_object`, `scale_points`, `shading.mask`, `src_w/disp_w`, `src_h/disp_h` already in scope.

UI-only task — verified manually.

- [ ] **Step 1: Import the helper**

In the imports block at the top of `app.py`, extend the existing regions import (`app.py:18`) from:

```python
from mini_highlight_advisor.regions import Region, scale_points, polygon_to_mask
```

to:

```python
from mini_highlight_advisor.regions import Region, scale_points, polygon_to_mask, polygons_to_mask
```

- [ ] **Step 2: Union every stroke instead of the last**

In the `Add region` handler, replace this block (`app.py:259-265`):

```python
                    objs = (canvas.json_data or {}).get("objects", []) if canvas else []
                    if not objs:
                        st.warning("Trace a lasso around an area on the image first.")
                    else:
                        pts = _points_from_object(objs[-1])
                        sx, sy = src_w / disp_w, src_h / disp_h
                        rmask = polygon_to_mask(scale_points(pts, sx, sy), (src_h, src_w)) & shading.mask
```

with:

```python
                    objs = (canvas.json_data or {}).get("objects", []) if canvas else []
                    if not objs:
                        st.warning("Trace a lasso around an area on the image first.")
                    else:
                        sx, sy = src_w / disp_w, src_h / disp_h
                        rings = [scale_points(_points_from_object(o), sx, sy) for o in objs]
                        rmask = polygons_to_mask(rings, (src_h, src_w)) & shading.mask
```

(The following `if not rmask.any(): ... else: book.add(...)` lines are unchanged.)

- [ ] **Step 3: Manual verification**

Run: `.venv/Scripts/python -m streamlit run app.py`
Then: upload a mini → "Draw a new region" → trace **two** separate loops over two different spots (e.g. both shoulders) → name it `Cloth` → Add region.
Expected: one region `Cloth` whose outline (left preview) encircles **both** spots; the paint-along steps treat them as a single region.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: union all lassos into one region on Add region"
```

---

### Task 7: Show hex + paste on palette slots (`app.py`)

**Files:**
- Modify: `app.py` (palette-slots loop, `app.py:328-359`)

**Interfaces:**
- Consumes: `palette.valid_hex` (Task 3); existing `slot_hex_{i}` / `slot_code_{i}` session keys, `collection.nearest_paint`, `_swatch`.

UI-only task — verified manually.

- [ ] **Step 1: Import `valid_hex`**

Extend the palette import block (`app.py:10-13`) to include `valid_hex`:

```python
from mini_highlight_advisor.palette import (
    DEFAULT_PALETTE, PaintColor, role_names, ramp_hex,
    default_coverage, remainder_pct, slider_max_pct, default_ramp, valid_hex,
)
```

- [ ] **Step 2: Custom slot — add hex text + paste, keep picker and nearest-paint**

In the palette loop, replace the custom-slot branch (`app.py:345-354`):

```python
            if slot_sel == CUSTOM:
                hexv = c2.color_picker(
                    f"hex {i + 1}", key=f"slot_hex_{i}", label_visibility="collapsed",
                )
                paint = PaintColor(f"Custom {i + 1}", hexv)
                palette.append(paint)
                near = collection.nearest_paint(paint.rgb, CATALOG)
                if near is not None:
                    owned_badge = "✅ owned" if near.code in set(picked) else "⚠️ not owned"
                    c3.caption(f"Closest: {near.name} · {near.paint_range or ''} · {near.code} ({owned_badge})")
```

with:

```python
            if slot_sel == CUSTOM:
                hexv = c2.color_picker(
                    f"hex {i + 1}", key=f"slot_hex_{i}", label_visibility="collapsed",
                )
                pasted = c3.text_input(
                    f"paste hex {i + 1}", value=hexv, key=f"slot_hexinput_{i}",
                    label_visibility="collapsed",
                )
                norm = valid_hex(pasted)
                if norm is None:
                    c3.caption("⚠️ invalid hex")
                elif norm != hexv:
                    st.session_state[f"slot_hex_{i}"] = norm
                    st.rerun()
                paint = PaintColor(f"Custom {i + 1}", hexv)
                palette.append(paint)
                near = collection.nearest_paint(paint.rgb, CATALOG)
                if near is not None:
                    owned_badge = "✅ owned" if near.code in set(picked) else "⚠️ not owned"
                    c3.caption(f"{hexv} · closest: {near.name} · {near.code} ({owned_badge})")
```

- [ ] **Step 3: Catalogue slot — show its hex as text**

In the catalogue-slot branch (`app.py:355-359`), change the owned line so the hex is visible. Replace:

```python
            else:
                paint = find_by_code(CATALOG, slot_sel)
                c2.markdown(_swatch(paint.hex, size="2.2em"), unsafe_allow_html=True)
                palette.append(paint)
                c3.write("✅ owned" if paint.code in set(picked) else "⚠️ not owned")
```

with:

```python
            else:
                paint = find_by_code(CATALOG, slot_sel)
                c2.markdown(_swatch(paint.hex, size="2.2em"), unsafe_allow_html=True)
                palette.append(paint)
                badge = "✅ owned" if paint.code in set(picked) else "⚠️ not owned"
                c3.write(f"{paint.hex} · {badge}")
```

- [ ] **Step 4: Manual verification**

Run: `.venv/Scripts/python -m streamlit run app.py`
Then: set a slot to `(custom target)` → the row shows the picker, a paste field pre-filled with the current hex, and a "closest paint" caption including the hex. Paste `#7a1f22` into the field → the picker swatch updates to that dark red and the closest-paint caption changes. Paste `nonsense` → "⚠️ invalid hex", picker unchanged. Set a slot to a catalogue paint → its hex string shows next to the owned badge.

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: show hex on every palette slot; paste a hex into custom slots"
```

---

### Task 8: "Blend neighbours" button on interior slots (`app.py`)

**Files:**
- Modify: `app.py` (palette-slots loop, inside the `for i in range(n)` body, `app.py:328-359`)

**Interfaces:**
- Consumes: `color.blend_hex_lab` (Task 4); `slot_hex_{i}` session keys, `CUSTOM`.

UI-only task — verified manually.

- [ ] **Step 1: Import `blend_hex_lab`**

Add near the other imports at the top of `app.py`:

```python
from mini_highlight_advisor.color import blend_hex_lab
```

- [ ] **Step 2: Add the button for interior slots**

At the **end** of the `for i in range(n):` loop body (after the `if slot_sel == CUSTOM: ... else: ...` block, still inside the loop), insert:

```python
            # Interior slots can be filled with the Lab-midpoint of their neighbours.
            if 0 < i < n - 1:
                if c1.button("↕ blend neighbours", key=f"blend_{i}"):
                    lo = st.session_state.get(f"slot_hex_{i - 1}", ramp_hex(i - 1, n))
                    hi = st.session_state.get(f"slot_hex_{i + 1}", ramp_hex(i + 1, n))
                    st.session_state[f"slot_hex_{i}"] = blend_hex_lab(lo, hi)
                    st.session_state[f"slot_code_{i}"] = CUSTOM
                    st.rerun()
```

- [ ] **Step 3: Manual verification**

Run: `.venv/Scripts/python -m streamlit run app.py`
Then: with 5 layers, set layer 3 to a dark colour and layer 5 to a light colour (both custom), then click "↕ blend neighbours" on **layer 4**.
Expected: layer 4 flips to `(custom target)` and its hex/picker become a colour visually midway between layers 3 and 5. The darkest (layer 1) and lightest (layer `n`) slots have **no** blend button.

- [ ] **Step 4: Full test-suite regression check**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all tests pass (existing suite + the new helper tests from Tasks 1–4).

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: blend an interior palette slot from its neighbours (Lab midpoint)"
```

---

## Self-Review

**Spec coverage:**
- A. Rename region → Task 2 (`set_name_at`) + Task 5 (UI). ✅
- B. Multi-lasso union → Task 1 (`polygons_to_mask`) + Task 6 (UI). ✅
- C. Hex show + paste + nearest paint → Task 3 (`valid_hex`) + Task 7 (UI). ✅
- D. Blend neighbours (Lab) → Task 4 (`blend_hex_lab`) + Task 8 (UI). ✅
- Non-goals (no engine change, Whole mini fixed, no reshape) respected — no task touches banding/lighting/edges; `set_name_at` and `remove` both reject index 0.

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows concrete code. UI tasks carry explicit manual-verification steps in place of unit tests (the editor is a Streamlit surface; this matches the repo's manual-smoke convention).

**Type consistency:** `polygons_to_mask(point_lists, shape)`, `set_name_at(g, name)`, `valid_hex(s) -> str|None`, `blend_hex_lab(h1, h2) -> str`, `lab_to_rgb(lab)`, `rgb_to_hex(rgb)` — names/signatures match between their defining task and their consuming UI task. `valid_hex` returns `str|None` and Task 7 branches on `None` accordingly. Custom-slot code column reuse: `c3` now hosts both the paste field and the caption — acceptable (Streamlit stacks them); noted so a reviewer isn't surprised.
