# Catalogue Growth + Paints/Inventory Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the bundled Vallejo catalogue safe to grow by hand (load-time validation + a format doc), and move paint inventory into its own "Paints" Streamlit tab, separate from the miniature-analysis workflow.

**Architecture:** The pure-data core stays Streamlit-free and unit-tested; `app.py` is the only Streamlit file. `pipeline.analyze` is untouched. This feature changes only (a) how robustly `catalog.py` loads the JSON, and (b) how the palette/inventory UI is arranged in `app.py`.

**Tech Stack:** Python 3.11, Streamlit, pytest. Test runner: `.venv/Scripts/python -m pytest`. The Streamlit app is verified manually.

## Global Constraints

Every task's requirements implicitly include these (verbatim from the spec):

- Offline / free at runtime — static bundled catalogue, no live lookups.
- Vallejo is the only catalogue brand for now (`brand == "Vallejo"`); catalogue hexes are approximate screen-swatches.
- Band range 3–5, default 5; `pipeline.analyze` untouched.
- `nearest_owned` is computed but never surfaced in the UI.
- Never build on `main`; feature branch + PR. This work is on `feat/catalogue-inventory` (forked from `feat/own-palette-input`).
- Test runner: `.venv/Scripts/python -m pytest`; the Streamlit app is verified manually.
- The shipped `vallejo_paints.json` content is **unchanged** by this feature (it stays the current 13-paint curated seed and grows later by hand).
- `brand` and `range` stay **optional** on load; `name` and `hex` are **required**. `PaintColor` and `find_by_name` are unchanged.

---

## File Structure

- `src/mini_highlight_advisor/catalog.py` — **modify**: add `validate_catalog` and call it inside `load_catalog`. Owns load-time integrity of the catalogue.
- `tests/test_catalog.py` — **modify**: add validation tests alongside the existing load/find tests.
- `docs/adding-paints.md` — **create**: hand-editing guide (schema, example row, hex rule, uniqueness rule).
- `app.py` — **modify**: wrap the body in two `st.tabs`, move "My paints" out of the sidebar into the Paints tab, add a readable owned list + catalogue-count line, remove the now-empty sidebar. Handle the tab-ordering gotcha.

---

## Task 1: Load-time catalogue validation

**Files:**
- Modify: `src/mini_highlight_advisor/catalog.py`
- Test: `tests/test_catalog.py`

**Interfaces:**
- Consumes: `PaintColor` from `.palette` (unchanged); the JSON shape `{"_note": ..., "paints": [{"name","hex","brand"?,"range"?}, ...]}`.
- Produces:
  - `validate_catalog(paints: list[dict]) -> None` — raises `ValueError` on the first bad entry; returns `None` when every entry is valid.
  - `load_catalog(path: Path = CATALOG_PATH) -> list[PaintColor]` — unchanged signature; now calls `validate_catalog` after JSON parse and before constructing `PaintColor`s.
  - `find_by_name` — unchanged.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_catalog.py` (keep the existing imports and tests; add the new import and the four new tests):

```python
import pytest

from mini_highlight_advisor.catalog import (
    load_catalog,
    find_by_name,
    validate_catalog,
)


def test_shipped_seed_passes_validation():
    # The curated seed must load cleanly (no regression).
    cat = load_catalog()
    assert len(cat) > 0
    assert all(p.brand == "Vallejo" for p in cat)


def test_missing_required_key_raises_naming_index():
    paints = [{"name": "Black", "hex": "#1b1b1b"}, {"name": "No Hex Here"}]
    with pytest.raises(ValueError) as exc:
        validate_catalog(paints)
    msg = str(exc.value)
    assert "1" in msg          # names the offending index
    assert "No Hex Here" in msg  # names the entry when name is present
    assert "hex" in msg          # names the missing key


def test_bad_hex_raises_quoting_value_and_name():
    paints = [{"name": "Bad Red", "hex": "#12"}]
    with pytest.raises(ValueError) as exc:
        validate_catalog(paints)
    msg = str(exc.value)
    assert "Bad Red" in msg
    assert "#12" in msg


def test_duplicate_name_raises_naming_duplicate():
    paints = [
        {"name": "Neutral Grey", "hex": "#6d7173"},
        {"name": "Neutral Grey", "hex": "#6d7174"},
    ]
    with pytest.raises(ValueError) as exc:
        validate_catalog(paints)
    assert "Neutral Grey" in str(exc.value)


def test_valid_paints_pass_validation():
    paints = [
        {"name": "Black", "hex": "#1b1b1b", "brand": "Vallejo", "range": "Model Color"},
        {"name": "Dead White", "hex": "#F3F3EE"},  # brand/range optional, hex case-insensitive
    ]
    assert validate_catalog(paints) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_catalog.py -v`
Expected: the four new tests FAIL / ERROR with `ImportError: cannot import name 'validate_catalog'`. The existing tests still pass.

- [ ] **Step 3: Write the implementation**

Edit `src/mini_highlight_advisor/catalog.py` to add the validator and call it. Full target content:

```python
from __future__ import annotations

import json
import re
from pathlib import Path

from .palette import PaintColor

CATALOG_PATH = Path(__file__).parent / "data" / "vallejo_paints.json"

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate_catalog(paints: list[dict]) -> None:
    """Raise ValueError on the first invalid entry; return None if all are valid.

    Checks, in order per entry: required keys present, hex well-formed,
    name unique. Error messages identify *which* entry is wrong so a hand-edit
    typo is actionable instead of crashing deep in the stack.
    """
    seen: set[str] = set()
    for i, p in enumerate(paints):
        if "name" not in p or "hex" not in p:
            missing = "name" if "name" not in p else "hex"
            present_name = p.get("name")
            label = f" (name={present_name!r})" if present_name is not None else ""
            raise ValueError(
                f"Catalogue entry at index {i}{label} is missing required key {missing!r}."
            )
        name = p["name"]
        hexv = p["hex"]
        if not _HEX_RE.match(hexv):
            raise ValueError(
                f"Catalogue paint {name!r} has invalid hex {hexv!r}; expected #rrggbb."
            )
        if name in seen:
            raise ValueError(f"Duplicate catalogue paint name {name!r}.")
        seen.add(name)


def load_catalog(path: Path = CATALOG_PATH) -> list[PaintColor]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    paints = data["paints"]
    validate_catalog(paints)
    return [
        PaintColor(
            name=p["name"],
            hex=p["hex"],
            brand=p.get("brand"),
            paint_range=p.get("range"),
        )
        for p in paints
    ]


def find_by_name(catalog: list[PaintColor], name: str) -> PaintColor | None:
    for p in catalog:
        if p.name == name:
            return p
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_catalog.py -v`
Expected: all tests PASS (the four new tests plus the four pre-existing ones).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/catalog.py tests/test_catalog.py
git commit -m "feat: validate catalogue at load time with entry-identifying errors"
```

---

## Task 2: "Adding paints" hand-edit guide

**Files:**
- Create: `docs/adding-paints.md`

**Interfaces:**
- Consumes: the schema and validation rules from Task 1 (so the doc's rules match the errors the code raises).
- Produces: none (documentation only; no test cycle).

- [ ] **Step 1: Create the doc**

Write `docs/adding-paints.md`:

````markdown
# Adding paints to the catalogue

The built-in Vallejo catalogue lives in
`src/mini_highlight_advisor/data/vallejo_paints.json`. Grow it by hand — add
one entry per paint to the `paints` array. No code change is needed; the app
picks up new entries on the next run.

## Schema

The file is a single JSON object:

```json
{
  "_note": "...",
  "paints": [
    {"name": "Neutral Grey", "brand": "Vallejo", "range": "Model Color", "hex": "#6d7173"}
  ]
}
```

Per entry:

- `name` — **required**. Must be **unique** across the whole file (the picker
  resolves paints by name and takes the first match, so duplicates break it).
- `hex` — **required**. Must be `#rrggbb` — a `#` followed by exactly six
  hex digits (`0-9`, `a-f`, `A-F`). Example: `#6d7173`. Case does not matter.
- `brand` — optional. Use `"Vallejo"` (the only catalogue brand for now).
- `range` — optional. e.g. `"Model Color"` or `"Game Color"`.

## Copy-paste example row

```json
    {"name": "Gory Red", "brand": "Vallejo", "range": "Game Color", "hex": "#7a1f1f"},
```

Paste it inside the `paints` array. Mind the commas: every entry except the
last needs a trailing comma.

## If you make a mistake

The catalogue is validated when the app loads. A bad entry produces a clear
error that names the offending paint (or its index if `name` is missing), so
you can find and fix it — a malformed hex, a missing `name`/`hex`, or a
duplicate name will each be reported rather than crashing or showing a wrong
colour.

## Scope

Hexes are approximate screen-swatches, not spectrophotometer-accurate. Target
coverage is Vallejo Model Color + Game Color. Other lines (Air, specialty) are
out of scope.
````

- [ ] **Step 2: Commit**

```bash
git add docs/adding-paints.md
git commit -m "docs: how to grow the paint catalogue by hand"
```

---

## Task 3: Two-tab UI (Miniature + Paints), sidebar removed

**Files:**
- Modify: `app.py`

**Interfaces:**
- Consumes: `load_catalog`, `find_by_name` (Task 1, unchanged signatures); `collection.load`/`collection.save`/`annotate_ownership`; `PaintColor`, `DEFAULT_PALETTE`, `role_names`; `analyze`; recipe helpers — all unchanged.
- Produces: none (Streamlit UI; verified manually per repo practice).

**Verified manually** (`.venv/Scripts/streamlit run app.py`), per repo practice — no unit test for `app.py`.

**Tab-ordering gotcha (must be handled):** `st.tabs` executes *both* tab bodies on every rerun, in **code order**. The Miniature badges read the owned set that the Paints multiselect produces. So the **Paints tab body is written before the Miniature tab body in code**, so `session_state["owned"]` and `owned_paints` are finalised before the Miniature badges render — no one-rerun-stale badge. Display order is fixed by the label list, so Miniature still appears first.

- [ ] **Step 1: Rewrite `app.py` with two tabs**

Replace the entire contents of `app.py` with:

```python
import os
import tempfile

import streamlit as st

from mini_highlight_advisor.catalog import load_catalog, find_by_name
from mini_highlight_advisor.collection import annotate_ownership
from mini_highlight_advisor import collection
from mini_highlight_advisor.masking import load_image
from mini_highlight_advisor.palette import DEFAULT_PALETTE, PaintColor, role_names
from mini_highlight_advisor.pipeline import analyze
from mini_highlight_advisor.recipes import load_all, to_palette, save_user, Recipe, RecipeStep

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

st.set_page_config(page_title="Mini Highlight Advisor", layout="wide")
st.title("Mini Highlight Advisor")
st.caption(
    "Upload a photo of a primed miniature (background-removed PNG is fastest). "
    "You'll get a painted preview + a paint-by-layer plan. Best on a well-lit, "
    "ideally zenithal-primed model."
)

CATALOG = load_catalog()
CATALOG_NAMES = [p.name for p in CATALOG]
CUSTOM = "(custom target)"

tab_mini, tab_paints = st.tabs(["🖌️ Miniature", "🎨 Paints"])

# NOTE: st.tabs runs BOTH bodies every rerun, in code order. Fill the Paints
# tab FIRST so owned_names / owned_paints are finalised before the Miniature
# tab renders its ownership badges. Display order (Miniature first) is fixed by
# the label list above, not by code order — do not reorder the labels.

# --- 🎨 Paints tab: inventory ---
with tab_paints:
    st.markdown("**My paints** (Vallejo)")
    owned_names = collection.load()
    picked = st.multiselect(
        "Paints you own", CATALOG_NAMES,
        default=sorted(owned_names & set(CATALOG_NAMES)),
        key="owned",
    )
    if set(picked) != owned_names:
        collection.save(set(picked))
    owned_paints = [p for name in picked if (p := find_by_name(CATALOG, name)) is not None]

    st.markdown("**Owned paints**")
    if not owned_paints:
        st.caption("No paints selected yet — tick the paints you own above.")
    for p in owned_paints:
        swatch = (
            f"<span style='display:inline-block;width:1em;height:1em;"
            f"background-color:{p.hex};border:1px solid #888;"
            f"vertical-align:middle;margin-right:0.5em'></span>"
        )
        rng = p.paint_range or ""
        st.markdown(f"{swatch}{p.name} · {rng}", unsafe_allow_html=True)

    st.caption(f"Catalogue: {len(CATALOG)} paints (Vallejo Model Color + Game Color)")

# --- 🖌️ Miniature tab: build the plan (unchanged behaviour) ---
with tab_mini:
    # --- recipe loader ---
    recipes = load_all()
    recipe_by_name = {r.name: r for r in recipes}
    choice = st.selectbox("Recipe", ["(none)"] + list(recipe_by_name))
    if st.button("Load") and choice != "(none)":
        pal = to_palette(recipe_by_name[choice])
        st.session_state["n"] = max(3, min(5, len(pal)))
        for i, p in enumerate(pal[:st.session_state["n"]]):
            st.session_state[f"slot_name_{i}"] = p.name if p.name in CATALOG_NAMES else CUSTOM
            st.session_state[f"slot_hex_{i}"] = p.hex
        st.rerun()

    # --- Palette slots (dark to light) ---
    # Seed "n" before the slider widget is created so the widget can own the value via key=
    # without a conflicting value= argument causing a session_state warning.
    st.session_state.setdefault("n", 5)
    n = st.slider("Number of layers", 3, 5, key="n")
    st.markdown("**Palette** (dark to light)")
    palette = []
    for i in range(n):
        default = DEFAULT_PALETTE[min(i, len(DEFAULT_PALETTE) - 1)]
        # Seed slot keys before the widgets that own them are created.
        st.session_state.setdefault(f"slot_name_{i}", default.name)
        st.session_state.setdefault(f"slot_hex_{i}", default.hex)
        default_name = st.session_state[f"slot_name_{i}"]
        if default_name not in CATALOG_NAMES:
            default_name = CUSTOM
        c1, c2, c3 = st.columns([3, 1, 1])
        sel = c1.selectbox(
            f"Layer {i + 1}", CATALOG_NAMES + [CUSTOM],
            index=(CATALOG_NAMES + [CUSTOM]).index(default_name), key=f"slot_name_{i}",
        )
        if sel == CUSTOM:
            hexv = c2.color_picker(
                f"hex {i + 1}", key=f"slot_hex_{i}", label_visibility="collapsed",
            )
            palette.append(PaintColor(f"Custom {i + 1}", hexv))
        else:
            paint = find_by_name(CATALOG, sel)
            if paint is None:
                seeded_hex = st.session_state.get(f"slot_hex_{i}", DEFAULT_PALETTE[min(i, len(DEFAULT_PALETTE) - 1)].hex)
                paint = PaintColor(sel, seeded_hex)
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
                     for r, p in zip(role_names(n), palette)]
            save_user(Recipe(rname.strip(), steps))
            st.success(f"Saved recipe '{rname.strip()}'.")

    uploaded = st.file_uploader("Mini photo", type=["png", "jpg", "jpeg"])
    if uploaded is not None:
        suffix = os.path.splitext(uploaded.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.getbuffer())
            tmp_path = tmp.name
        try:
            with st.spinner("Analyzing (first run downloads the depth model if no alpha channel)..."):
                rgb, alpha = load_image(tmp_path)
                result = analyze(rgb, alpha, palette)
            st.image(result.panel, caption="Original | Painted preview | Highlight plan", use_container_width=True)
            st.subheader("Layer guide (paint dark to light)")
            for role, paint, cov in zip(result.roles, palette, result.coverage):
                st.markdown(f"**{role}** - {paint.name}  ·  ~{cov:.0f}% of the model")
            st.subheader("Paint-along steps")
            st.caption("Work dark to light. 'Where to paint' = the whole zone for this paint "
                       "(bright marker); 'Apply across' = that same whole zone in the paint colour; "
                       "'Stays this colour' = the smaller slice that remains this colour after you paint "
                       "the lighter layers over the rest.")
            for step, role, paint, cov in zip(result.steps, result.roles, palette, result.coverage):
                cum_cov = sum(result.coverage[step.index:])
                st.markdown(f"**Step {step.index + 1} — {role} · {paint.name}**")
                if step.is_last:
                    c1, c2 = st.columns(2)
                    c1.image(step.zone_rgb, caption="Where to paint", use_container_width=True)
                    c2.image(step.cumulative_rgb, caption=f"Apply across — whole area (~{cum_cov:.0f}%)", use_container_width=True)
                else:
                    c1, c2, c3 = st.columns(3)
                    c1.image(step.zone_rgb, caption="Where to paint", use_container_width=True)
                    c2.image(step.cumulative_rgb, caption=f"Apply across — whole area (~{cum_cov:.0f}%)", use_container_width=True)
                    c3.image(step.exact_rgb, caption=f"Stays this colour — final (~{cov:.0f}%)", use_container_width=True)
        finally:
            os.unlink(tmp_path)
```

Notes on the change vs. the current file:
- The sidebar block (`st.sidebar.markdown(...)` + `st.sidebar.multiselect(...)`) is **gone**; its logic moved verbatim into the `tab_paints` block as a plain `st.multiselect` (same `key="owned"`, same `collection.load`/`save`, same `owned_paints` comprehension).
- Everything that was top-level main-body code (recipe loader → slider → palette slots → save-as-recipe → uploader) is now indented under `with tab_mini:` — behaviour unchanged.
- `owned_paints` is computed in the `tab_paints` block, which runs first in code order, so the Miniature badges see the up-to-date owned set in the same rerun.

- [ ] **Step 2: Sanity-check the module imports**

Run: `.venv/Scripts/python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read()); print('app.py parses OK')"`
Expected: `app.py parses OK` (catches indentation/syntax slips before launching Streamlit).

- [ ] **Step 3: Manual verification (per repo practice)**

Launch: `.venv/Scripts/streamlit run app.py`, then walk the acceptance criteria:

- **AC5 (two tabs, Miniature unchanged):** Two tabs show — 🖌️ Miniature (first, default) and 🎨 Paints. On the Miniature tab: pick a recipe/layers, upload a mini photo → preview panel + layer guide + paint-along steps all render as before.
- **AC6 (My paints moved + persists):** "My paints" is on the Paints tab (not in a sidebar; there is no sidebar). Tick some paints, stop the app, relaunch → the same paints are still ticked (persisted to `user_data/collection.json`).
- **AC7 (readable inventory + count):** The Paints tab shows each owned paint as a colour swatch + name + range, and a line like *"Catalogue: 13 paints (Vallejo Model Color + Game Color)"*.
- **AC8 (tab-ordering, no stale badge):** On the Paints tab, tick a paint that matches a Miniature layer, switch to the Miniature tab → its badge reads ✅ owned in the **same** interaction (not one rerun late). Untick it → badge flips to ⚠️ not owned, again same-session.
- **AC1 (catalogue growth):** Add one valid entry to `vallejo_paints.json`, refresh the app → the new paint appears in both the Miniature layer picker and the Paints multiselect, with no code change, and the catalogue-count line increments.
- **AC9 (carried constraint):** `nearest_owned` appears nowhere in the UI.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: split UI into Miniature + Paints tabs; move inventory out of sidebar"
```

---

## Self-Review

**Spec coverage:**
- Component 1 (catalogue data & format): JSON unchanged (Global Constraints); `docs/adding-paints.md` → Task 2. ✅
- Component 2 (load-time validation): `validate_catalog` + `load_catalog` wiring + tests → Task 1. ✅
- Component 3 (two-tab UI + readable inventory + count line + sidebar removal): Task 3. ✅
- Component 4 (data-flow + tab-ordering gotcha): called out and implemented in Task 3 (Paints body before Miniature body). ✅
- Acceptance criteria: AC1, AC5–AC9 → Task 3 manual walk-through; AC2–AC4 → Task 1 tests. ✅
- Testing strategy: unit tests (Task 1) + manual verification (Task 3). ✅

**Placeholder scan:** No TBD/TODO/"handle edge cases"/"write tests for the above" — every code and test step has concrete content. ✅

**Type consistency:** `validate_catalog(paints: list[dict]) -> None` and `load_catalog(path) -> list[PaintColor]` are used identically in Task 1's code and tests. `owned_paints` (list[PaintColor]), `CATALOG_NAMES` (list[str]), `find_by_name`/`annotate_ownership` signatures match the existing modules read during planning. `paint_range` (not `range`) is the `PaintColor` attribute used in the swatch line. ✅
