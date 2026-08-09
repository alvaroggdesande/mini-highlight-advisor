# Catalogue Code-Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make paint `code` the unique identity across the app so true product names can repeat, add a hex→nearest-paint suggestion, and fix the inconsistent colour box.

**Architecture:** `PaintColor` gains an optional `code` field; catalogue validation keys uniqueness on `code`; the Streamlit UI stores/searches by `code` with a `format_func` display of `Name · Range · code`; the buggy disabled `st.color_picker` for catalogue slots is replaced by a deterministic inline HTML swatch; ownership migrates from names to codes with a backward-compat shim.

**Tech Stack:** Python 3.11, Streamlit, NumPy, pytest. Files under `src/mini_highlight_advisor/`, UI in `app.py`, data JSON in `src/mini_highlight_advisor/data/`.

## Global Constraints

- Branch: `feat/own-palette-input` (continue; do NOT branch or merge). Feature branch + PR later; never build on `main`.
- `code` is the unique identity key; names may duplicate across ranges.
- `PaintColor` positional construction `PaintColor(name, hex, brand, paint_range)` is used across tests and `to_palette` — `code` MUST be added as the LAST field with a default (`code: str = ""`) so all existing positional calls stay valid.
- Recipe `paint_ref` stays a name string (best-effort resolution only). No recipe schema migration.
- Hex swatch style must match the Paints-tab pattern: `border:1px solid #888` so dark colours stay visible on the dark theme.
- Run tests with `.venv/Scripts/python -m pytest`. Streamlit UI has no unit harness — verify UI tasks manually with `streamlit run app.py`.

---

### Task 1: Add `code` to `PaintColor` and `find_by_code`

**Files:**
- Modify: `src/mini_highlight_advisor/palette.py` (add field + codes on `DEFAULT_PALETTE`)
- Modify: `src/mini_highlight_advisor/catalog.py` (add `find_by_code`, populate `code` in `load_catalog`)
- Test: `tests/test_catalog.py`, `tests/test_palette.py`

**Interfaces:**
- Produces: `PaintColor(name, hex, brand=None, paint_range=None, code="")`; `find_by_code(catalog: list[PaintColor], code: str) -> PaintColor | None`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_palette.py`:

```python
def test_paintcolor_has_code_default_empty():
    from mini_highlight_advisor.palette import PaintColor
    p = PaintColor("Custom 1", "#123456")
    assert p.code == ""


def test_default_palette_entries_have_codes():
    from mini_highlight_advisor.palette import DEFAULT_PALETTE
    assert all(p.code for p in DEFAULT_PALETTE)
```

Add to `tests/test_catalog.py`:

```python
def test_find_by_code_resolves_known_paint():
    from mini_highlight_advisor.catalog import load_catalog, find_by_code
    p = find_by_code(load_catalog(), "72.045")
    assert p is not None and p.name == "Charred Brown"


def test_find_by_code_missing_returns_none():
    from mini_highlight_advisor.catalog import load_catalog, find_by_code
    assert find_by_code(load_catalog(), "99.999") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_palette.py tests/test_catalog.py -k "code" -v`
Expected: FAIL (`TypeError`/`AttributeError` for `code`; `find_by_code` not defined).

- [ ] **Step 3: Add the `code` field (last, defaulted)**

In `src/mini_highlight_advisor/palette.py`, change the dataclass fields to:

```python
@dataclass(frozen=True)
class PaintColor:
    name: str
    hex: str
    brand: str | None = None
    paint_range: str | None = None
    code: str = ""
```

And add `code=` to each `DEFAULT_PALETTE` entry:

```python
DEFAULT_PALETTE = [
    PaintColor("Black", "#1b1b1b", "Vallejo", "Model Color", code="70.950"),
    PaintColor("German Grey", "#3f4442", "Vallejo", "Model Color", code="70.995"),
    PaintColor("Neutral Grey", "#6d7173", "Vallejo", "Model Color", code="70.991"),
    PaintColor("Light Grey", "#a7a9a6", "Vallejo", "Model Color", code="70.990"),
    PaintColor("Dead White", "#f3f3ee", "Vallejo", "Model Color", code="70.951"),
]
```

- [ ] **Step 4: Populate `code` in `load_catalog` and add `find_by_code`**

In `src/mini_highlight_advisor/catalog.py`, add `code=p["code"]` to the `PaintColor(...)` construction in `load_catalog`, and append:

```python
def find_by_code(catalog: list[PaintColor], code: str) -> PaintColor | None:
    for p in catalog:
        if p.code == code:
            return p
    return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_palette.py tests/test_catalog.py -k "code" -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mini_highlight_advisor/palette.py src/mini_highlight_advisor/catalog.py tests/test_palette.py tests/test_catalog.py
git commit -m "feat: add PaintColor.code identity field and find_by_code"
```

---

### Task 2: Validate catalogue uniqueness on `code` (allow duplicate names)

**Files:**
- Modify: `src/mini_highlight_advisor/catalog.py:14-38` (`validate_catalog`)
- Test: `tests/test_catalog.py`

**Interfaces:**
- Consumes: `PaintColor.code` (Task 1).
- Produces: `validate_catalog(paints: list[dict]) -> None` — requires `code`,`name`,`hex`; raises on duplicate `code`; permits duplicate `name`.

- [ ] **Step 1: Update the failing/renamed tests**

In `tests/test_catalog.py`: DELETE `test_duplicate_name_raises_naming_duplicate`. Replace/adjust the dict-based tests to include `code`, and add duplicate-code + duplicate-name-allowed cases:

```python
def test_missing_required_key_raises_naming_index():
    paints = [
        {"code": "70.950", "name": "Black", "hex": "#1b1b1b"},
        {"code": "70.999", "name": "No Hex Here"},
    ]
    with pytest.raises(ValueError) as exc:
        validate_catalog(paints)
    msg = str(exc.value)
    assert "1" in msg and "No Hex Here" in msg and "hex" in msg


def test_missing_code_raises():
    paints = [{"name": "Black", "hex": "#1b1b1b"}]
    with pytest.raises(ValueError) as exc:
        validate_catalog(paints)
    assert "code" in str(exc.value)


def test_bad_hex_raises_quoting_value_and_name():
    paints = [{"code": "70.957", "name": "Bad Red", "hex": "#12"}]
    with pytest.raises(ValueError) as exc:
        validate_catalog(paints)
    msg = str(exc.value)
    assert "Bad Red" in msg and "#12" in msg


def test_duplicate_code_raises():
    paints = [
        {"code": "70.991", "name": "Neutral Grey", "hex": "#6d7173"},
        {"code": "70.991", "name": "Other Grey", "hex": "#6d7174"},
    ]
    with pytest.raises(ValueError) as exc:
        validate_catalog(paints)
    assert "70.991" in str(exc.value)


def test_duplicate_name_is_allowed():
    paints = [
        {"code": "70.951", "name": "Dead White", "hex": "#f3f3ee"},
        {"code": "72.001", "name": "Dead White", "hex": "#ffffff"},
    ]
    assert validate_catalog(paints) is None


def test_valid_paints_pass_validation():
    paints = [
        {"code": "70.950", "name": "Black", "hex": "#1b1b1b", "brand": "Vallejo", "range": "Model Color"},
        {"code": "70.951", "name": "Dead White", "hex": "#F3F3EE"},
    ]
    assert validate_catalog(paints) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_catalog.py -v`
Expected: FAIL (validator still rejects on name / does not require code).

- [ ] **Step 3: Rewrite `validate_catalog`**

Replace the body in `src/mini_highlight_advisor/catalog.py`:

```python
def validate_catalog(paints: list[dict]) -> None:
    """Raise ValueError on the first invalid entry; return None if all valid.

    Per entry: required keys (code, name, hex) present, hex well-formed,
    code unique. Names MAY repeat across ranges. Errors identify the entry.
    """
    seen_codes: set[str] = set()
    for i, p in enumerate(paints):
        for key in ("code", "name", "hex"):
            if key not in p:
                present = p.get("name") or p.get("code")
                label = f" ({present!r})" if present is not None else ""
                raise ValueError(
                    f"Catalogue entry at index {i}{label} is missing required key {key!r}."
                )
        code, name, hexv = p["code"], p["name"], p["hex"]
        if not _HEX_RE.match(hexv):
            raise ValueError(
                f"Catalogue paint {name!r} ({code}) has invalid hex {hexv!r}; expected #rrggbb."
            )
        if code in seen_codes:
            raise ValueError(f"Duplicate catalogue paint code {code!r} (name {name!r}).")
        seen_codes.add(code)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_catalog.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/catalog.py tests/test_catalog.py
git commit -m "feat: validate catalogue uniqueness on code, allow duplicate names"
```

---

### Task 3: Revert the 7 mangled paint names

**Files:**
- Modify: `src/mini_highlight_advisor/data/vallejo_paints.json`
- Test: `tests/test_catalog.py`

**Interfaces:**
- Consumes: validator from Task 2 (duplicate names now allowed).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_catalog.py`:

```python
def test_reverted_names_collide_but_load_by_code():
    from mini_highlight_advisor.catalog import load_catalog, find_by_code
    cat = load_catalog()
    # Two "Dead White" now coexist, distinguished only by code.
    assert find_by_code(cat, "70.951").name == "Dead White"      # Model Color
    assert find_by_code(cat, "72.001").name == "Dead White"      # Game Color
    assert find_by_code(cat, "72.061").name == "Khaki"           # was "Khaki game"
    assert find_by_code(cat, "72.016").name == "Royal Purple"    # was "Royal Purple model"→ Game
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_catalog.py::test_reverted_names_collide_but_load_by_code -v`
Expected: FAIL (names still mangled).

- [ ] **Step 3: Revert the 7 names in `vallejo_paints.json`**

Change only the `name` values (codes/hexes unchanged):

| Code | Old name | New name |
|------|----------|----------|
| 70.951 | `White (Dead White)` | `Dead White` |
| 70.810 | `Royal Purple model` | `Royal Purple` |
| 72.040 | `Leather Brown game` | `Leather Brown` |
| 72.051 | `Black game color` | `Black` |
| 72.043 | `Beige Brown game` | `Beige Brown` |
| 72.064 | `Yellow Olive game` | `Yellow Olive` |
| 72.061 | `Khaki game` | `Khaki` |

- [ ] **Step 4: Run the full catalogue tests to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_catalog.py -v`
Expected: PASS (all, including `test_shipped_seed_passes_validation`).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/data/vallejo_paints.json tests/test_catalog.py
git commit -m "data: revert mangled paint names now that identity is code"
```

---

### Task 4: Ownership stored by code + legacy name→code shim

**Files:**
- Modify: `src/mini_highlight_advisor/collection.py:14-24` (`load`, `save`)
- Modify: `user_data/collection.json` (migrate names → codes)
- Test: `tests/test_collection.py`

**Interfaces:**
- Consumes: `PaintColor.code`, catalogue list.
- Produces: `load(path=COLLECTION_PATH, catalog: list[PaintColor] | None = None) -> set[str]` — returns stored strings as-is when `catalog is None`; when a catalogue is given, keeps known codes, maps a legacy name to its code only when that name is unique in the catalogue, and drops anything else. `save(owned: set[str], path=...)` unchanged (now holds codes).

- [ ] **Step 1: Update/replace collection tests**

In `tests/test_collection.py` replace the name-based round-trip and add shim tests (keep the `annotate`/`nearest_owned` tests as they are — they use ad-hoc `PaintColor`s):

```python
from mini_highlight_advisor.collection import load, save, annotate_ownership
from mini_highlight_advisor.palette import PaintColor


def test_save_then_load_round_trips_codes(tmp_path):
    p = tmp_path / "collection.json"
    save({"70.804", "72.010"}, path=p)
    assert load(path=p) == {"70.804", "72.010"}


def test_load_missing_returns_empty_set(tmp_path):
    assert load(path=tmp_path / "nope.json") == set()


def test_load_maps_unique_legacy_name_and_drops_unknown(tmp_path):
    p = tmp_path / "collection.json"
    p.write_text('{"owned": ["Beige Red", "72.010", "Ghost Paint"]}', encoding="utf-8")
    catalog = [
        PaintColor("Beige Red", "#EAA88C", "Vallejo", "Model Color", code="70.804"),
        PaintColor("Bloody Red", "#C72323", "Vallejo", "Game Color", code="72.010"),
    ]
    # "Beige Red"->70.804 (unique name), "72.010" kept (known code), "Ghost Paint" dropped.
    assert load(path=p, catalog=catalog) == {"70.804", "72.010"}


def test_load_drops_ambiguous_legacy_name(tmp_path):
    p = tmp_path / "collection.json"
    p.write_text('{"owned": ["Dead White"]}', encoding="utf-8")
    catalog = [
        PaintColor("Dead White", "#f3f3ee", "Vallejo", "Model Color", code="70.951"),
        PaintColor("Dead White", "#ffffff", "Vallejo", "Game Color", code="72.001"),
    ]
    assert load(path=p, catalog=catalog) == set()  # ambiguous -> dropped
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_collection.py -v`
Expected: FAIL (`load` takes no `catalog`; old round-trip removed).

- [ ] **Step 3: Rewrite `load` with the shim**

In `src/mini_highlight_advisor/collection.py`, add `from collections import Counter` at the top and replace `load`:

```python
def load(path: Path = COLLECTION_PATH, catalog: list[PaintColor] | None = None) -> set[str]:
    path = Path(path)
    if not path.exists():
        return set()
    stored = set(json.loads(path.read_text(encoding="utf-8")).get("owned", []))
    if catalog is None:
        return stored
    codes = {p.code for p in catalog}
    name_counts = Counter(p.name for p in catalog)
    by_name = {p.name: p.code for p in catalog}
    result: set[str] = set()
    for entry in stored:
        if entry in codes:
            result.add(entry)
        elif name_counts.get(entry) == 1:
            result.add(by_name[entry])
        # otherwise: unknown or ambiguous legacy name -> drop
    return result
```

(`save` is unchanged.)

- [ ] **Step 4: Migrate the personal collection file**

Overwrite `user_data/collection.json` with codes:

```json
{
  "owned": [
    "70.804",
    "70.950",
    "72.010",
    "72.028",
    "70.984",
    "72.007",
    "70.863",
    "72.009",
    "70.858",
    "70.918",
    "70.988",
    "70.990",
    "70.991",
    "72.042",
    "72.032",
    "72.029",
    "70.997"
  ]
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_collection.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mini_highlight_advisor/collection.py user_data/collection.json tests/test_collection.py
git commit -m "feat: store ownership by code with legacy name->code shim"
```

---

### Task 5: Shared `nearest_paint` helper (nearest-in-catalogue seam)

**Files:**
- Modify: `src/mini_highlight_advisor/collection.py:34-45` (`annotate_ownership`, add `nearest_paint`)
- Test: `tests/test_collection.py`

**Interfaces:**
- Produces: `nearest_paint(target_rgb: np.ndarray, candidates: list[PaintColor]) -> PaintColor | None` — RGB-closest candidate, or `None` if empty. `annotate_ownership` reuses it for `nearest_owned`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_collection.py`:

```python
def test_nearest_paint_returns_rgb_closest():
    from mini_highlight_advisor.collection import nearest_paint
    cands = [PaintColor("Orange Brown", "#A75A38"), PaintColor("Black", "#000000")]
    got = nearest_paint(PaintColor("t", "#E15E32").rgb, cands)
    assert got.name == "Orange Brown"


def test_nearest_paint_empty_returns_none():
    from mini_highlight_advisor.collection import nearest_paint
    import numpy as np
    assert nearest_paint(np.zeros(3, dtype="float32"), []) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_collection.py -k nearest_paint -v`
Expected: FAIL (`nearest_paint` not defined).

- [ ] **Step 3: Add `nearest_paint` and refactor `annotate_ownership`**

In `src/mini_highlight_advisor/collection.py`:

```python
def nearest_paint(target_rgb: np.ndarray, candidates: list[PaintColor]) -> PaintColor | None:
    if not candidates:
        return None
    return min(candidates, key=lambda c: float(np.linalg.norm(c.rgb - target_rgb)))


def annotate_ownership(palette: list[PaintColor], owned: list[PaintColor]) -> list[SlotStatus]:
    owned_names = {p.name for p in owned}
    slots: list[SlotStatus] = []
    for paint in palette:
        is_owned = paint.name in owned_names
        nearest = None if is_owned else nearest_paint(paint.rgb, owned)
        slots.append(SlotStatus(paint=paint, owned=is_owned, nearest_owned=nearest))
    return slots
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_collection.py -v`
Expected: PASS (including the existing `nearest_owned` tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/collection.py tests/test_collection.py
git commit -m "refactor: extract nearest_paint helper for catalogue suggestions"
```

---

### Task 6: Paints tab — code-based multiselect + inventory (UI)

**Files:**
- Modify: `app.py:35-60` (Paints tab block)

**Interfaces:**
- Consumes: `find_by_code` (Task 1), `collection.load(catalog=...)`/`save` (Task 4).
- Produces: `owned_paints: list[PaintColor]`, `picked: list[str]` (codes) — both read by the Miniature tab (Task 7).

**Note:** No unit harness for Streamlit — verify manually at Step 3.

- [ ] **Step 1: Rewrite the Paints tab block**

Replace lines 36–60 (`with tab_paints:` body) in `app.py`. First, near the top imports, add `find_by_code` to the catalog import and add a shared label helper after `CATALOG` is loaded:

```python
from mini_highlight_advisor.catalog import load_catalog, find_by_name, find_by_code
...
CATALOG = load_catalog()
CUSTOM = "(custom target)"
CODE_LABEL = {p.code: f"{p.name} · {p.paint_range or ''} · {p.code}" for p in CATALOG}
CATALOG_CODES = [p.code for p in CATALOG]


def _swatch(hexv: str, size: str = "1em") -> str:
    return (
        f"<span style='display:inline-block;width:{size};height:{size};"
        f"background-color:{hexv};border:1px solid #888;"
        f"vertical-align:middle;margin-right:0.5em'></span>"
    )
```

Then the tab body:

```python
with tab_paints:
    st.markdown("**My paints** (Vallejo)")
    owned_codes = collection.load(catalog=CATALOG)
    picked = st.multiselect(
        "Paints you own", CATALOG_CODES,
        default=sorted(owned_codes & set(CATALOG_CODES)),
        format_func=lambda c: CODE_LABEL.get(c, c),
        key="owned",
    )
    if set(picked) != owned_codes:
        collection.save(set(picked))
    owned_paints = [p for c in picked if (p := find_by_code(CATALOG, c)) is not None]

    st.markdown("**Owned paints**")
    if not owned_paints:
        st.caption("No paints selected yet — tick the paints you own above.")
    for p in owned_paints:
        rng = p.paint_range or ""
        st.markdown(f"{_swatch(p.hex)}{p.name} · {rng} · {p.code}", unsafe_allow_html=True)

    st.caption(f"Catalogue: {len(CATALOG)} paints (Vallejo Model Color + Game Color)")
```

Remove the now-unused `CATALOG_NAMES = [p.name for p in CATALOG]` line if nothing else needs it (Task 7 will confirm).

- [ ] **Step 2: Confirm the module still imports**

Run: `.venv/Scripts/python -c "import ast; ast.parse(open('app.py',encoding='utf-8').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Manual UI verification**

Run: `streamlit run app.py`. In the **Paints** tab confirm:
- The multiselect shows `Name · Range · code`; the 17 migrated paints are pre-ticked.
- Typing a **code** (e.g. `70.804`) filters to that paint; typing a range (`Game Color`) filters too.
- "Owned paints" lists each with a colour swatch and its code.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: Paints tab searches and stores paints by code"
```

---

### Task 7: Miniature tab — swatch fix, code selectbox, hex→nearest (UI)

**Files:**
- Modify: `app.py:62-120` (Miniature tab: recipe load, palette slots, save-as-recipe)

**Interfaces:**
- Consumes: `CODE_LABEL`, `CATALOG_CODES`, `CUSTOM`, `_swatch`, `find_by_code`, `find_by_name`, `collection.nearest_paint`, `annotate_ownership`, `picked` (Task 6).

**Note:** No unit harness — verify manually at Step 3. This task fixes the colour-box bug by replacing the disabled `st.color_picker` for catalogue slots with `_swatch(...)`.

- [ ] **Step 1: Rewrite recipe-load to seed codes**

In the recipe loader, resolve `paint_ref` name → code only when unique:

```python
    recipes = load_all()
    recipe_by_name = {r.name: r for r in recipes}
    name_counts = Counter(p.name for p in CATALOG)  # add: from collections import Counter
    choice = st.selectbox("Recipe", ["(none)"] + list(recipe_by_name))
    if st.button("Load") and choice != "(none)":
        pal = to_palette(recipe_by_name[choice])
        st.session_state["n"] = max(3, min(5, len(pal)))
        for i, p in enumerate(pal[:st.session_state["n"]]):
            match = find_by_name(CATALOG, p.name)
            unique = name_counts.get(p.name) == 1
            st.session_state[f"slot_code_{i}"] = match.code if (match and unique) else CUSTOM
            st.session_state[f"slot_hex_{i}"] = p.hex
        st.rerun()
```

- [ ] **Step 2: Rewrite the palette-slots loop**

Replace the slot loop body so session keys hold codes, catalogue slots draw `_swatch`, and custom slots show the nearest-catalogue suggestion:

```python
    st.session_state.setdefault("n", 5)
    n = st.slider("Number of layers", 3, 5, key="n")
    st.markdown("**Palette** (dark to light)")
    palette = []
    options = CATALOG_CODES + [CUSTOM]
    for i in range(n):
        default = DEFAULT_PALETTE[min(i, len(DEFAULT_PALETTE) - 1)]
        st.session_state.setdefault(f"slot_code_{i}", default.code)
        st.session_state.setdefault(f"slot_hex_{i}", default.hex)
        default_code = st.session_state[f"slot_code_{i}"]
        if default_code != CUSTOM and find_by_code(CATALOG, default_code) is None:
            default_code = CUSTOM
        c1, c2, c3 = st.columns([3, 1, 1])
        sel = c1.selectbox(
            f"Layer {i + 1}", options,
            index=options.index(default_code),
            format_func=lambda c: CUSTOM if c == CUSTOM else CODE_LABEL.get(c, c),
            key=f"slot_code_{i}",
        )
        if sel == CUSTOM:
            hexv = c2.color_picker(
                f"hex {i + 1}", key=f"slot_hex_{i}", label_visibility="collapsed",
            )
            paint = PaintColor(f"Custom {i + 1}", hexv)
            palette.append(paint)
            near = collection.nearest_paint(paint.rgb, CATALOG)
            if near is not None:
                owned_badge = "✅ owned" if near.code in set(picked) else "⚠️ not owned"
                c3.caption(f"Closest: {near.name} · {near.paint_range or ''} · {near.code} ({owned_badge})")
        else:
            paint = find_by_code(CATALOG, sel)
            c2.markdown(_swatch(paint.hex, size="2.2em"), unsafe_allow_html=True)
            palette.append(paint)
            status = annotate_ownership([paint], owned_paints)[0]
            c3.write("✅ owned" if status.owned else "⚠️ not owned")
```

- [ ] **Step 3: Update save-as-recipe to use code presence**

`paint_ref` should be the name only for catalogue paints (which carry a code):

```python
        if st.button("Save recipe") and rname.strip():
            steps = [RecipeStep(label=r, hex=p.hex, paint_ref=(p.name if p.code else None))
                     for r, p in zip(role_names(n), palette)]
            save_user(Recipe(rname.strip(), steps))
            st.success(f"Saved recipe '{rname.strip()}'.")
```

Also delete the now-unused `CATALOG_NAMES` binding if no remaining reference (grep `CATALOG_NAMES` in `app.py`).

- [ ] **Step 4: Confirm the module still parses**

Run: `.venv/Scripts/python -c "import ast; ast.parse(open('app.py',encoding='utf-8').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 5: Manual UI verification**

Run: `streamlit run app.py`. In the **Miniature** tab confirm:
- Each catalogue layer shows a **solid colour swatch** that updates immediately when you change the paint (the old stale/blank box is gone), including dark colours (visible border).
- Selecting `(custom target)` shows an editable colour picker AND a `Closest: Name · Range · code (owned/not owned)` caption that updates as you change the hex.
- Load **NMM Copper**: steps whose `paint_ref` isn't in the catalogue (`Bright Orange`) fall to custom with the recipe hex — no crash; catalogue steps resolve to their swatch.
- Owned/not-owned badge is correct against your ticked paints.

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "fix: reliable colour swatch, code-based slots, hex->nearest suggestion"
```

---

## Self-Review

**Spec coverage:**
- §1 identity/`code` → Task 1. §2 validation-on-code → Task 2. §3 Paints tab search+inventory → Task 6. §4 colour-box fix + hex→nearest + code selectbox → Task 7. §5 ownership migration + shim → Task 4. §6 recipes best-effort → Task 7 Step 1. §7 name revert → Task 3. §8 tests → folded into Tasks 1,2,3,4,5. Nearest-in-catalogue helper → Task 5. All covered.

**Placeholder scan:** No TBD/TODO/"add error handling"/"similar to Task N"; every code step has concrete code.

**Type consistency:** `PaintColor(..., code="")` last-field default is used consistently; `find_by_code`/`nearest_paint`/`load(catalog=...)` signatures match across producing and consuming tasks; `CODE_LABEL`/`CATALOG_CODES`/`CUSTOM`/`_swatch` defined in Task 6 and consumed in Task 7; session keys renamed `slot_name_*`→`slot_code_*` uniformly (old `view_hex_*` disabled-picker removed).

**Known dependency note:** Tasks 6–7 modify `app.py` and are not unit-tested; they carry explicit manual verification steps. Tasks 1–5 are TDD with pytest.
