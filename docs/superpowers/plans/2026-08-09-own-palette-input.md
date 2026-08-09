# Own-Palette Input (#4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the raw hex-per-slot palette editor with a Vallejo catalogue-backed picker, save/load recipes, and an owned-paints collection with a flag-only "not owned" badge — the enabler for paint-mixing (#3).

**Architecture:** Pure-data core (no Streamlit): extend `PaintColor` with `brand`/`range`; add `catalog.py` (bundled Vallejo JSON), `recipes.py` (Recipe dataclass + builtin/user JSON), `collection.py` (owned set + `annotate_ownership`). `pipeline.analyze` is untouched — this only changes how the palette is assembled before `analyze` runs. `app.py` gains a sidebar "My paints" manager and a reworked palette section.

**Tech Stack:** Python 3.11, dataclasses, numpy, Streamlit, pytest. Data is static JSON shipped in the package (`src/mini_highlight_advisor/data/`) plus local `user_data/` for the user's collection and saved recipes.

## Global Constraints

- **Offline / free at runtime** — no live API lookups; catalogue is a static bundled JSON.
- **Primed / monochrome minis only; whole mini = one region** — unchanged; `analyze` untouched.
- **Vallejo is the only catalogue brand** for v1 (`brand == "Vallejo"`); it seeds #5.
- **Catalogue hexes are approximate screen-swatches**, not exact — label as such in the JSON and a code comment.
- **Band range 3–5, default 5** — matches `role_names`; recipe length must fall in this range.
- **Never build on `main`.** Work happens on branch `feat/own-palette-input` (already created).
- **Test runner:** `.venv/Scripts/python -m pytest`. The Streamlit app is verified **manually** (`streamlit run app.py`), not unit-tested (repo practice).
- **`nearest_owned` is computed but NEVER surfaced in the UI** — it is the #3 seam only.

Spec: `docs/superpowers/specs/2026-08-09-own-palette-input-design.md`.

## File Structure

- `src/mini_highlight_advisor/palette.py` — **modify**: `PaintColor` gains optional `brand` / `paint_range`; `DEFAULT_PALETTE` → Vallejo greys.
- `src/mini_highlight_advisor/data/vallejo_paints.json` — **create**: bundled catalogue.
- `src/mini_highlight_advisor/catalog.py` — **create**: load catalogue, `find_by_name`.
- `src/mini_highlight_advisor/data/recipes_builtin.json` — **create**: starter recipes (NMM Copper).
- `src/mini_highlight_advisor/recipes.py` — **create**: `RecipeStep`, `Recipe`, load/save/merge, `to_palette`.
- `src/mini_highlight_advisor/collection.py` — **create**: owned set load/save, `SlotStatus`, `annotate_ownership`.
- `app.py` — **modify**: sidebar "My paints" + reworked palette section.
- `tests/test_palette.py` — **modify**: new-field + Vallejo-default tests.
- `tests/test_catalog.py`, `tests/test_recipes.py`, `tests/test_collection.py` — **create**.

---

### Task 1: Extend `PaintColor` and switch `DEFAULT_PALETTE` to Vallejo

**Files:**
- Modify: `src/mini_highlight_advisor/palette.py:8-25`
- Test: `tests/test_palette.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `PaintColor(name: str, hex: str, brand: str | None = None, paint_range: str | None = None)`, frozen, with unchanged `.rgb` property. `DEFAULT_PALETTE: list[PaintColor]` — 5 Vallejo greys, ascending brightness, each `brand="Vallejo"`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_palette.py`:

```python
def test_paintcolor_optional_brand_range():
    p = PaintColor("Neutral Grey", "#6d7173", brand="Vallejo", paint_range="Model Color")
    assert p.brand == "Vallejo"
    assert p.paint_range == "Model Color"


def test_paintcolor_still_constructs_with_name_hex_only():
    p = PaintColor("White", "#ffffff")
    assert p.brand is None and p.paint_range is None
    assert np.allclose(p.rgb, [255, 255, 255])


def test_default_palette_is_vallejo():
    assert len(DEFAULT_PALETTE) == 5
    assert all(c.brand == "Vallejo" for c in DEFAULT_PALETTE)
    lums = [c.rgb.mean() for c in DEFAULT_PALETTE]
    assert lums == sorted(lums)  # dark to light
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_palette.py -v`
Expected: FAIL — `PaintColor` has no `brand`/`paint_range`; `DEFAULT_PALETTE` entries have `brand is None`.

- [ ] **Step 3: Implement**

In `palette.py`, replace the `PaintColor` dataclass and `DEFAULT_PALETTE`:

```python
@dataclass(frozen=True)
class PaintColor:
    name: str
    hex: str
    brand: str | None = None
    paint_range: str | None = None

    @property
    def rgb(self) -> np.ndarray:
        h = self.hex.lstrip("#")
        return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


# Vallejo greyscale ramp (dark -> light). Hexes are approximate screen-swatches.
DEFAULT_PALETTE = [
    PaintColor("Black", "#1b1b1b", "Vallejo", "Model Color"),
    PaintColor("German Grey", "#3f4442", "Vallejo", "Model Color"),
    PaintColor("Neutral Grey", "#6d7173", "Vallejo", "Model Color"),
    PaintColor("Light Grey", "#a7a9a6", "Vallejo", "Model Color"),
    PaintColor("Dead White", "#f3f3ee", "Vallejo", "Model Color"),
]
```

Add `from __future__ import annotations` at the top if not present (it is not — add it) so `str | None` works on 3.11.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_palette.py -v`
Expected: PASS (including the pre-existing palette tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/palette.py tests/test_palette.py
git commit -m "feat: PaintColor brand/range fields + Vallejo default palette"
```

---

### Task 2: Bundled Vallejo catalogue + `catalog.py`

**Files:**
- Create: `src/mini_highlight_advisor/data/vallejo_paints.json`
- Create: `src/mini_highlight_advisor/catalog.py`
- Test: `tests/test_catalog.py`

**Interfaces:**
- Consumes: `PaintColor` (Task 1).
- Produces:
  - `CATALOG_PATH: Path`
  - `load_catalog(path: Path = CATALOG_PATH) -> list[PaintColor]`
  - `find_by_name(catalog: list[PaintColor], name: str) -> PaintColor | None`

- [ ] **Step 1: Create the seed catalogue JSON**

Create `src/mini_highlight_advisor/data/vallejo_paints.json`. This is a **small curated seed** (greyscale ramp + a few metals + the NMM-copper colours). Hexes are approximate. Grow this file later with zero code change — sourcing a fuller Vallejo range is optional and out of scope for this task's tests.

```json
{
  "_note": "Approximate screen-swatch hexes, not spectrophotometer-accurate. Vallejo only; seed for multi-brand DB (#5).",
  "paints": [
    {"name": "Black", "brand": "Vallejo", "range": "Model Color", "hex": "#1b1b1b"},
    {"name": "German Grey", "brand": "Vallejo", "range": "Model Color", "hex": "#3f4442"},
    {"name": "Neutral Grey", "brand": "Vallejo", "range": "Model Color", "hex": "#6d7173"},
    {"name": "Light Grey", "brand": "Vallejo", "range": "Model Color", "hex": "#a7a9a6"},
    {"name": "Dead White", "brand": "Vallejo", "range": "Model Color", "hex": "#f3f3ee"},
    {"name": "Oily Steel", "brand": "Vallejo", "range": "Model Color", "hex": "#565a5e"},
    {"name": "Gunmetal Grey", "brand": "Vallejo", "range": "Model Color", "hex": "#42474b"},
    {"name": "Silver", "brand": "Vallejo", "range": "Model Color", "hex": "#c9cccd"},
    {"name": "Charred Brown", "brand": "Vallejo", "range": "Game Color", "hex": "#3D2A25"},
    {"name": "Orange Brown", "brand": "Vallejo", "range": "Model Color", "hex": "#A75A38"},
    {"name": "Bright Orange", "brand": "Vallejo", "range": "Game Color", "hex": "#E15E32"},
    {"name": "Beige Red", "brand": "Vallejo", "range": "Model Color", "hex": "#EAA88C"},
    {"name": "Off-White", "brand": "Vallejo", "range": "Model Color", "hex": "#F5F5F3"}
  ]
}
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_catalog.py`:

```python
import numpy as np
from mini_highlight_advisor.catalog import load_catalog, find_by_name
from mini_highlight_advisor.palette import DEFAULT_PALETTE


def test_load_catalog_returns_vallejo_paints():
    cat = load_catalog()
    assert len(cat) > 0
    assert all(p.brand == "Vallejo" for p in cat)


def test_known_paint_resolves_to_expected_hex():
    cat = load_catalog()
    charred = find_by_name(cat, "Charred Brown")
    assert charred is not None
    assert charred.hex.lower() == "#3d2a25"
    assert charred.paint_range == "Game Color"


def test_find_by_name_missing_returns_none():
    assert find_by_name(load_catalog(), "Nonexistent Paint") is None


def test_default_palette_entries_exist_in_catalog():
    cat = load_catalog()
    for p in DEFAULT_PALETTE:
        assert find_by_name(cat, p.name) is not None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_catalog.py -v`
Expected: FAIL — `mini_highlight_advisor.catalog` does not exist.

- [ ] **Step 4: Implement `catalog.py`**

Create `src/mini_highlight_advisor/catalog.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from .palette import PaintColor

CATALOG_PATH = Path(__file__).parent / "data" / "vallejo_paints.json"


def load_catalog(path: Path = CATALOG_PATH) -> list[PaintColor]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        PaintColor(
            name=p["name"],
            hex=p["hex"],
            brand=p.get("brand"),
            paint_range=p.get("range"),
        )
        for p in data["paints"]
    ]


def find_by_name(catalog: list[PaintColor], name: str) -> PaintColor | None:
    for p in catalog:
        if p.name == name:
            return p
    return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_catalog.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mini_highlight_advisor/data/vallejo_paints.json src/mini_highlight_advisor/catalog.py tests/test_catalog.py
git commit -m "feat: bundled Vallejo catalogue + catalog loader"
```

---

### Task 3: `recipes.py` + builtin recipes JSON

**Files:**
- Create: `src/mini_highlight_advisor/data/recipes_builtin.json`
- Create: `src/mini_highlight_advisor/recipes.py`
- Test: `tests/test_recipes.py`

**Interfaces:**
- Consumes: `PaintColor` (Task 1).
- Produces:
  - `@dataclass(frozen=True) RecipeStep(label: str, hex: str, paint_ref: str | None = None)`
  - `@dataclass(frozen=True) Recipe(name: str, steps: list[RecipeStep])`
  - `BUILTIN_PATH: Path`, `USER_PATH: Path`
  - `load_builtin(path: Path = BUILTIN_PATH) -> list[Recipe]`
  - `load_user(path: Path = USER_PATH) -> list[Recipe]` (returns `[]` if file missing)
  - `save_user(recipe: Recipe, path: Path = USER_PATH) -> None` (upsert by name)
  - `load_all(builtin_path=BUILTIN_PATH, user_path=USER_PATH) -> list[Recipe]` (builtin then user)
  - `to_palette(recipe: Recipe) -> list[PaintColor]`

- [ ] **Step 1: Create the builtin recipes JSON**

Create `src/mini_highlight_advisor/data/recipes_builtin.json`:

```json
{
  "recipes": [
    {
      "name": "NMM Copper",
      "steps": [
        {"label": "Shadow", "hex": "#3D2A25", "paint_ref": "Charred Brown"},
        {"label": "Base", "hex": "#A75A38", "paint_ref": "Orange Brown"},
        {"label": "Midtone", "hex": "#E15E32", "paint_ref": "Bright Orange"},
        {"label": "Highlight", "hex": "#EAA88C", "paint_ref": "Beige Red"},
        {"label": "Edge Highlight", "hex": "#F5F5F3", "paint_ref": "Off-White"}
      ]
    }
  ]
}
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_recipes.py`:

```python
from pathlib import Path

from mini_highlight_advisor.recipes import (
    Recipe, RecipeStep, load_builtin, load_user, save_user, load_all, to_palette,
)


def test_load_builtin_has_nmm_copper_dark_to_light():
    recipes = load_builtin()
    copper = next(r for r in recipes if r.name == "NMM Copper")
    assert len(copper.steps) == 5
    assert 3 <= len(copper.steps) <= 5
    lums = [sum(int(s.hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) for s in copper.steps]
    assert lums == sorted(lums)  # dark to light


def test_to_palette_uses_paint_ref_name_and_hex():
    recipe = Recipe("t", [RecipeStep("Base", "#A75A38", "Orange Brown"),
                          RecipeStep("Top", "#ffffff", None)])
    pal = to_palette(recipe)
    assert pal[0].name == "Orange Brown" and pal[0].hex == "#A75A38"
    assert pal[1].name == "Top" and pal[1].hex == "#ffffff"


def test_save_user_then_load_user_round_trips(tmp_path):
    p = tmp_path / "recipes.json"
    r = Recipe("My Scheme", [RecipeStep("Base", "#123456", None)])
    save_user(r, path=p)
    loaded = load_user(path=p)
    assert [x.name for x in loaded] == ["My Scheme"]
    assert loaded[0].steps[0].hex == "#123456"


def test_save_user_upserts_by_name(tmp_path):
    p = tmp_path / "recipes.json"
    save_user(Recipe("A", [RecipeStep("s", "#111111", None)]), path=p)
    save_user(Recipe("A", [RecipeStep("s", "#222222", None)]), path=p)
    loaded = load_user(path=p)
    assert len(loaded) == 1 and loaded[0].steps[0].hex == "#222222"


def test_load_user_missing_file_returns_empty(tmp_path):
    assert load_user(path=tmp_path / "nope.json") == []


def test_load_all_merges_builtin_and_user(tmp_path):
    p = tmp_path / "recipes.json"
    save_user(Recipe("Custom", [RecipeStep("s", "#333333", None)]), path=p)
    names = [r.name for r in load_all(user_path=p)]
    assert "NMM Copper" in names and "Custom" in names
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_recipes.py -v`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement `recipes.py`**

Create `src/mini_highlight_advisor/recipes.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .palette import PaintColor

BUILTIN_PATH = Path(__file__).parent / "data" / "recipes_builtin.json"
USER_PATH = Path(__file__).resolve().parents[2] / "user_data" / "recipes.json"


@dataclass(frozen=True)
class RecipeStep:
    label: str
    hex: str
    paint_ref: str | None = None


@dataclass(frozen=True)
class Recipe:
    name: str
    steps: list[RecipeStep]


def _parse(data: dict) -> list[Recipe]:
    return [
        Recipe(r["name"], [RecipeStep(s["label"], s["hex"], s.get("paint_ref")) for s in r["steps"]])
        for r in data.get("recipes", [])
    ]


def load_builtin(path: Path = BUILTIN_PATH) -> list[Recipe]:
    return _parse(json.loads(Path(path).read_text(encoding="utf-8")))


def load_user(path: Path = USER_PATH) -> list[Recipe]:
    path = Path(path)
    if not path.exists():
        return []
    return _parse(json.loads(path.read_text(encoding="utf-8")))


def save_user(recipe: Recipe, path: Path = USER_PATH) -> None:
    path = Path(path)
    existing = [r for r in load_user(path) if r.name != recipe.name]
    existing.append(recipe)
    payload = {"recipes": [
        {"name": r.name, "steps": [
            {"label": s.label, "hex": s.hex, "paint_ref": s.paint_ref} for s in r.steps
        ]} for r in existing
    ]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_all(builtin_path: Path = BUILTIN_PATH, user_path: Path = USER_PATH) -> list[Recipe]:
    return load_builtin(builtin_path) + load_user(user_path)


def to_palette(recipe: Recipe) -> list[PaintColor]:
    return [PaintColor(name=s.paint_ref or s.label, hex=s.hex) for s in recipe.steps]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_recipes.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mini_highlight_advisor/data/recipes_builtin.json src/mini_highlight_advisor/recipes.py tests/test_recipes.py
git commit -m "feat: recipes (builtin + user) with save/load and to_palette"
```

---

### Task 4: `collection.py` — owned set + `annotate_ownership`

**Files:**
- Create: `src/mini_highlight_advisor/collection.py`
- Test: `tests/test_collection.py`

**Interfaces:**
- Consumes: `PaintColor` (Task 1).
- Produces:
  - `COLLECTION_PATH: Path`
  - `load(path: Path = COLLECTION_PATH) -> set[str]` (owned paint names; `set()` if missing)
  - `save(owned: set[str], path: Path = COLLECTION_PATH) -> None`
  - `@dataclass(frozen=True) SlotStatus(paint: PaintColor, owned: bool, nearest_owned: PaintColor | None)`
  - `annotate_ownership(palette: list[PaintColor], owned: list[PaintColor]) -> list[SlotStatus]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_collection.py`:

```python
from mini_highlight_advisor.collection import load, save, annotate_ownership
from mini_highlight_advisor.palette import PaintColor


def test_save_then_load_round_trips(tmp_path):
    p = tmp_path / "collection.json"
    save({"Orange Brown", "Beige Red"}, path=p)
    assert load(path=p) == {"Orange Brown", "Beige Red"}


def test_load_missing_returns_empty_set(tmp_path):
    assert load(path=tmp_path / "nope.json") == set()


def test_annotate_marks_owned_and_unowned():
    palette = [PaintColor("Orange Brown", "#A75A38"), PaintColor("Bright Orange", "#E15E32")]
    owned = [PaintColor("Orange Brown", "#A75A38")]
    slots = annotate_ownership(palette, owned)
    assert slots[0].owned is True
    assert slots[1].owned is False


def test_nearest_owned_is_closest_by_rgb():
    # unowned target #E15E32; owned has a near-orange and a far-black
    palette = [PaintColor("Bright Orange", "#E15E32")]
    owned = [PaintColor("Orange Brown", "#A75A38"), PaintColor("Black", "#000000")]
    slots = annotate_ownership(palette, owned)
    assert slots[0].owned is False
    assert slots[0].nearest_owned.name == "Orange Brown"


def test_nearest_owned_none_when_no_owned():
    slots = annotate_ownership([PaintColor("X", "#123456")], [])
    assert slots[0].owned is False
    assert slots[0].nearest_owned is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_collection.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `collection.py`**

Create `src/mini_highlight_advisor/collection.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .palette import PaintColor

COLLECTION_PATH = Path(__file__).resolve().parents[2] / "user_data" / "collection.json"


def load(path: Path = COLLECTION_PATH) -> set[str]:
    path = Path(path)
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")).get("owned", []))


def save(owned: set[str], path: Path = COLLECTION_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"owned": sorted(owned)}, indent=2), encoding="utf-8")


@dataclass(frozen=True)
class SlotStatus:
    paint: PaintColor
    owned: bool
    nearest_owned: PaintColor | None


def annotate_ownership(palette: list[PaintColor], owned: list[PaintColor]) -> list[SlotStatus]:
    owned_names = {p.name for p in owned}
    slots: list[SlotStatus] = []
    for paint in palette:
        is_owned = paint.name in owned_names
        nearest = None
        # nearest_owned: closest owned paint by Euclidean RGB distance.
        # COMPUTED FOR THE #3 (mixing) SEAM — do not surface in the UI.
        if not is_owned and owned:
            nearest = min(owned, key=lambda o: float(np.linalg.norm(o.rgb - paint.rgb)))
        slots.append(SlotStatus(paint=paint, owned=is_owned, nearest_owned=nearest))
    return slots
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_collection.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: PASS (all pre-existing tests still green; `analyze` untouched).

- [ ] **Step 6: Commit**

```bash
git add src/mini_highlight_advisor/collection.py tests/test_collection.py
git commit -m "feat: owned-paints collection + annotate_ownership (nearest_owned seam)"
```

---

### Task 5: Wire the app — "My paints" sidebar + reworked palette section

**Files:**
- Modify: `app.py` (replace lines 20-28, the current slider + hex-slot palette block; keep the upload/analyze/render block below intact)

**Interfaces:**
- Consumes: `load_catalog`, `find_by_name` (Task 2); `load_all`, `to_palette`, `Recipe`, `RecipeStep`, `save_user` (Task 3); `collection.load`, `collection.save`, `annotate_ownership` (Task 4); `DEFAULT_PALETTE`, `PaintColor` (Task 1).
- Produces: a `palette: list[PaintColor]` fed to `analyze(...)` exactly as today.

This task is **verified manually** (Streamlit), not unit-tested. Implement the full replacement, then run the app and walk the checklist.

- [ ] **Step 1: Replace the palette block in `app.py`**

Replace the imports block and lines 20-28 (the `n = st.sidebar.slider(...)` through the `palette.append(...)` loop). Keep everything from `uploaded = st.file_uploader(...)` downward unchanged.

New imports (top of file, alongside existing ones):

```python
from mini_highlight_advisor.catalog import load_catalog, find_by_name
from mini_highlight_advisor.recipes import load_all, to_palette, save_user, Recipe, RecipeStep
from mini_highlight_advisor import collection
from mini_highlight_advisor.collection import annotate_ownership
```

New palette-assembly block (replaces old lines 20-28):

```python
CATALOG = load_catalog()
CATALOG_NAMES = [p.name for p in CATALOG]
CUSTOM = "(custom target)"

# --- Sidebar: My paints (owned collection) ---
st.sidebar.markdown("**My paints** (Vallejo)")
owned_names = collection.load()
picked = st.sidebar.multiselect(
    "Paints you own", CATALOG_NAMES, default=sorted(owned_names & set(CATALOG_NAMES)),
    key="owned",
)
if set(picked) != owned_names:
    collection.save(set(picked))
owned_paints = [find_by_name(CATALOG, name) for name in picked]

# --- Main: recipe loader ---
recipes = load_all()
recipe_by_name = {r.name: r for r in recipes}
choice = st.selectbox("Load recipe", ["(none)"] + list(recipe_by_name))
if st.button("Load recipe") and choice != "(none)":
    pal = to_palette(recipe_by_name[choice])
    st.session_state["n"] = len(pal)
    for i, p in enumerate(pal):
        st.session_state[f"slot_name_{i}"] = p.name if p.name in CATALOG_NAMES else CUSTOM
        st.session_state[f"slot_hex_{i}"] = p.hex
    st.rerun()

# --- Palette slots (dark to light) ---
n = st.slider("Number of layers", 3, 5, st.session_state.get("n", 5), key="n")
st.markdown("**Palette** (dark to light)")
palette = []
for i in range(n):
    default = DEFAULT_PALETTE[min(i, len(DEFAULT_PALETTE) - 1)]
    default_name = st.session_state.get(f"slot_name_{i}", default.name)
    if default_name not in CATALOG_NAMES:
        default_name = CUSTOM
    c1, c2, c3 = st.columns([3, 1, 1])
    sel = c1.selectbox(
        f"Layer {i + 1}", CATALOG_NAMES + [CUSTOM],
        index=(CATALOG_NAMES + [CUSTOM]).index(default_name), key=f"slot_name_{i}",
    )
    if sel == CUSTOM:
        hexv = c2.color_picker(
            f"hex {i + 1}", value=st.session_state.get(f"slot_hex_{i}", default.hex),
            key=f"slot_hex_{i}", label_visibility="collapsed",
        )
        palette.append(PaintColor(f"Custom {i + 1}", hexv))
    else:
        paint = find_by_name(CATALOG, sel)
        c2.color_picker(f"hex {i + 1}", value=paint.hex, key=f"view_hex_{i}",
                        disabled=True, label_visibility="collapsed")
        palette.append(paint)
    # owned badge for this slot
    status = annotate_ownership([palette[-1]], owned_paints)[0]
    c3.write("✅ owned" if status.owned else "⚠️ not owned")

# --- Save current palette as a recipe ---
with st.expander("Save as recipe"):
    rname = st.text_input("Recipe name", key="save_name")
    if st.button("Save recipe") and rname.strip():
        steps = [RecipeStep(label=r, hex=p.hex, paint_ref=(p.name if p.name in CATALOG_NAMES else None))
                 for r, p in zip(__import__("mini_highlight_advisor.palette", fromlist=["role_names"]).role_names(n), palette)]
        save_user(Recipe(rname.strip(), steps))
        st.success(f"Saved recipe '{rname.strip()}'.")
```

Note on the `role_names` import: replace the inline `__import__(...)` with a clean top-of-file import `from mini_highlight_advisor.palette import DEFAULT_PALETTE, PaintColor, role_names` and use `role_names(n)` directly. (Inline import shown only to make the dependency explicit; use the clean import.)

**Streamlit gotcha to expect:** a widget with `key="n"` will warn if you also pass a default `value=` while `st.session_state["n"]` already exists. Since the "Load recipe" branch sets `st.session_state["n"]` then `st.rerun()`, prefer letting the widget own `n` via its key and seed session_state *before* the widget is first created (e.g. `st.session_state.setdefault("n", 5)` at the top, then `st.slider("Number of layers", 3, 5, key="n")` with no `value=`). The same before-widget-creation rule applies to the `slot_name_*` / `slot_hex_*` keys. This is the one place expected to need live iteration during manual verification.

- [ ] **Step 2: Launch the app**

Run: `streamlit run app.py`

- [ ] **Step 3: Manual verification checklist** (maps to spec acceptance criteria)

Confirm each:
- [ ] Picking a Vallejo paint from a Layer dropdown auto-shows its hex (no typing). *(AC1)*
- [ ] Choosing `(custom target)` shows an editable colour picker. *(AC2)*
- [ ] Ticking paints under sidebar "My paints", restarting the app → selections persist (`user_data/collection.json` exists). *(AC3)*
- [ ] "Load recipe" → NMM Copper sets layers to 5 and fills all slots with the copper colours dark→light. *(AC4)*
- [ ] "Save as recipe" with a name → restart → it appears in the Load recipe list alongside NMM Copper (`user_data/recipes.json`). *(AC5)*
- [ ] Each slot shows ✅/⚠️ driven by what's ticked in "My paints". *(AC6)*
- [ ] Uploading a mini still produces the preview + steps exactly as before. *(AC8)*
- [ ] `nearest_owned` appears nowhere in the UI. *(AC7)*

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: app palette section — Vallejo picker, recipes, owned badges"
```

---

## Self-Review

**Spec coverage:**
- Data model (`Paint`/`Recipe`/owned) → Tasks 1, 2, 3, 4. ✅
- Recipe carries own length, load sets band count 1:1 → Task 5 load block + Task 3 (3–5 guard tested). ✅
- Files (bundled catalogue + builtin recipes committed; `user_data/` local) → Tasks 2, 3, 4. ✅
- Builtin+user merged, save writes user file → `load_all` + `save_user` (Task 3), app uses them (Task 5). ✅
- Modules: extend `palette.py`, add `catalog.py`/`recipes.py`/`collection.py`; `analyze` untouched → Tasks 1–4; Task 4 Step 5 runs full suite to confirm `analyze` unaffected. ✅
- `annotate_ownership` + `nearest_owned` computed not surfaced → Task 4 impl + Task 5 AC7 check. ✅
- UI: sidebar "My paints" + main picker/recipe/badge/save; hex editor demoted to `(custom target)` → Task 5. ✅
- Out-of-scope (mixing, nearest_owned display, multi-brand, coverage sliders, band cap>5, online fetch) → none of these appear in any task. ✅

**Placeholder scan:** No TBD/TODO; all code blocks concrete; catalogue/recipe JSON given in full. The only "approximate" content is catalogue hexes, which the spec explicitly designates approximate. ✅

**Type consistency:** `PaintColor(name, hex, brand=None, paint_range=None)` used identically in Tasks 1/2/3/5. `find_by_name(catalog, name)`, `load_catalog`, `load_all`, `to_palette`, `save_user`, `collection.load/save`, `annotate_ownership(palette, owned)` names/signatures match across producing task and Task 5 consumption. `SlotStatus.owned` / `.nearest_owned` read in tests (Task 4) and app (Task 5). ✅
