# Global Content and Export/Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add curated global demo content (built-in recipes, sample photos, demo projects) always accessible from the deployed app, and add export/import for user recipes and paint collection so data survives redeployment.

**Architecture:** Core export/import functions added to existing `recipes.py` and `collection.py` (pure Python, no Streamlit). A new `samples.py` module discovers sample files from `data/samples/` at import time. UI additions land in `colour_panel.py` (recipe manage), `paints_tab.py` (collection backup), `app.py` (sample photos picker), and `projects_panel.py` (sample project loader). All sample/global content committed under `src/mini_highlight_advisor/data/` so it's present in every deployment.

**Tech Stack:** Python 3.11, Streamlit, `json`/`pathlib` stdlib only (no new dependencies).

**Spec:** Conversation-driven (no formal spec file). Branch: `feat/global-content-and-export`.

## Global Constraints

- Python 3.11; `.venv/Scripts/python -m pytest` to run tests; `streamlit run app.py` to run app
- Never push to `main`; feature branch + PR only (`feat/global-content-and-export`)
- All new UI strings need a key in **both** `locales/en.json` AND `locales/es.json`
- No new third-party dependencies
- Do not modify `user_data/` persistence paths — user saves remain local-only

---

### Task 1: Recipe export/import — core functions

**Files:**
- Modify: `src/mini_highlight_advisor/recipes.py`
- Test: `tests/test_recipes.py`

**Interfaces:**
- Produces: `export_to_json_bytes(recipes: list[Recipe]) -> bytes`
- Produces: `import_from_json_bytes(data: bytes) -> list[Recipe]`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_recipes.py` (after existing tests):

```python
import json as _json
from mini_highlight_advisor.recipes import (
    export_to_json_bytes, import_from_json_bytes, Recipe, RecipeStep,
)

def test_export_import_round_trips():
    original = [Recipe("Test", [RecipeStep("Base", "#ff0000", "Red Paint")])]
    data = export_to_json_bytes(original)
    result = import_from_json_bytes(data)
    assert len(result) == 1
    assert result[0].name == "Test"
    assert result[0].steps[0].hex == "#ff0000"
    assert result[0].steps[0].paint_ref == "Red Paint"

def test_export_empty_list():
    data = export_to_json_bytes([])
    result = import_from_json_bytes(data)
    assert result == []

def test_import_preserves_paint_ref_none():
    r = Recipe("NoPaintRef", [RecipeStep("Base", "#aabbcc")])  # paint_ref defaults to None
    result = import_from_json_bytes(export_to_json_bytes([r]))
    assert result[0].steps[0].paint_ref is None

def test_import_from_json_bytes_malformed_raises():
    import pytest
    with pytest.raises(Exception):
        import_from_json_bytes(b"not valid json {{{")

def test_export_produces_valid_json():
    r = Recipe("Gold", [RecipeStep("Shadow", "#1a1a1a", "Black")])
    data = export_to_json_bytes([r])
    parsed = _json.loads(data)
    assert "recipes" in parsed
    assert parsed["recipes"][0]["name"] == "Gold"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd C:\Users\ag\alvaro\git\mini-highlight-advisor
.venv/Scripts/python -m pytest tests/test_recipes.py -k "export or import" -v
```

Expected: FAIL with `ImportError` (functions not yet defined).

- [ ] **Step 3: Implement the two functions**

In `src/mini_highlight_advisor/recipes.py`, add after `load_all`:

```python
def export_to_json_bytes(recipes: list[Recipe]) -> bytes:
    payload = {"recipes": [
        {"name": r.name, "steps": [
            {"label": s.label, "hex": s.hex, "paint_ref": s.paint_ref}
            for s in r.steps
        ]}
        for r in recipes
    ]}
    return json.dumps(payload, indent=2).encode("utf-8")


def import_from_json_bytes(data: bytes) -> list[Recipe]:
    return _parse(json.loads(data.decode("utf-8")))
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv/Scripts/python -m pytest tests/test_recipes.py -v
```

Expected: all `test_recipes.py` tests PASS.

- [ ] **Step 5: Commit**

```
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor checkout -b feat/global-content-and-export
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor add src/mini_highlight_advisor/recipes.py tests/test_recipes.py
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor commit -m "feat: add recipe export/import core functions"
```

---

### Task 2: Recipe export/import — UI

**Files:**
- Modify: `ui/colour_panel.py`
- Modify: `locales/en.json`
- Modify: `locales/es.json`

**Interfaces:**
- Consumes: `export_to_json_bytes`, `import_from_json_bytes`, `load_user` from `mini_highlight_advisor.recipes` (Task 1)
- Produces: `_render_recipe_manager()` private function called from `render()`

- [ ] **Step 1: Add i18n keys**

In `locales/en.json`, inside the `"colour"` object, add:

```json
"manage_recipes_expander": "Manage recipes",
"download_recipes_btn": "⬇ Download my_recipes.json",
"import_recipes_label": "Import recipes (.json)",
"recipes_imported_toast": "Imported {count} recipe(s)",
"import_recipes_error": "Import failed: {err}"
```

In `locales/es.json`, inside the `"colour"` object, add:

```json
"manage_recipes_expander": "Gestionar recetas",
"download_recipes_btn": "⬇ Descargar mis_recetas.json",
"import_recipes_label": "Importar recetas (.json)",
"recipes_imported_toast": "Se importaron {count} receta(s)",
"import_recipes_error": "Error al importar: {err}"
```

- [ ] **Step 2: Update the import line in colour_panel.py**

Find the existing import line (line 14):
```python
from mini_highlight_advisor.recipes import load_all, to_palette, save_user, Recipe, RecipeStep
```

Replace with:
```python
from mini_highlight_advisor.recipes import (
    load_all, load_user, to_palette, save_user,
    export_to_json_bytes, import_from_json_bytes,
    Recipe, RecipeStep,
)
```

- [ ] **Step 3: Add `_render_recipe_manager` function**

Add the following new private function at the bottom of `ui/colour_panel.py` (before the existing helpers like `_apply_ramp`):

```python
_RECIPE_IMPORT_NONCE = "_recipe_import_nonce"


def _render_recipe_manager() -> None:
    with st.expander(t("colour.manage_recipes_expander")):
        user_recipes = load_user()
        if user_recipes:
            st.download_button(
                t("colour.download_recipes_btn"),
                data=export_to_json_bytes(user_recipes),
                file_name="my_recipes.json",
                mime="application/json",
                key="_recipe_dl_btn",
            )

        nonce = st.session_state.get(_RECIPE_IMPORT_NONCE, 0)
        uploader_key = f"_recipe_import_{nonce}"

        def _on_import():
            uploaded = st.session_state.get(uploader_key)
            if uploaded is None:
                return
            try:
                imported = import_from_json_bytes(uploaded.read())
                for r in imported:
                    save_user(r)
                st.session_state[_RECIPE_IMPORT_NONCE] = nonce + 1
                st.session_state["_recipe_import_count"] = len(imported)
            except Exception as exc:
                st.session_state["_recipe_import_err"] = str(exc)

        st.file_uploader(
            t("colour.import_recipes_label"),
            type=["json"],
            key=uploader_key,
            on_change=_on_import,
        )
        if count := st.session_state.pop("_recipe_import_count", None):
            st.toast(t("colour.recipes_imported_toast", count=count))
        if err := st.session_state.pop("_recipe_import_err", None):
            st.error(t("colour.import_recipes_error", err=err))
```

- [ ] **Step 4: Call `_render_recipe_manager()` from `render()`**

In the `render()` function, after `_render_scheme_save(book)` and before the deferred rerun block, add:

```python
    _render_recipe_manager()
```

The end of `render()` should look like:
```python
    _render_scheme_save(book)
    _render_recipe_manager()

    _deferred = st.session_state.pop("_ramp_applied", False)
    ...
```

- [ ] **Step 5: Smoke-test manually**

Run `streamlit run app.py`, open the Colour panel, scroll to the bottom. Verify:
- "Manage recipes" expander appears
- If you have saved recipes, a download button appears
- The import uploader appears and accepts .json files

- [ ] **Step 6: Commit**

```
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor add ui/colour_panel.py locales/en.json locales/es.json
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor commit -m "feat: recipe export/import UI in colour panel"
```

---

### Task 3: Collection export/import — core functions

**Files:**
- Modify: `src/mini_highlight_advisor/collection.py`
- Test: `tests/test_collection.py`

**Interfaces:**
- Produces: `export_to_json_bytes(owned: set[str]) -> bytes`
- Produces: `import_from_json_bytes(data: bytes, catalog: list[PaintColor] | None = None) -> set[str]`
- Internal change: extract `_validate_codes` helper (keeps `load()` behaviour identical, removes duplication)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_collection.py` (after existing tests):

```python
import json as _json
from mini_highlight_advisor.collection import (
    export_to_json_bytes, import_from_json_bytes,
)
from mini_highlight_advisor.palette import PaintColor

def test_export_collection_round_trips():
    owned = {"72.112", "70.888"}
    data = export_to_json_bytes(owned)
    result = import_from_json_bytes(data)
    assert result == owned

def test_export_empty_set():
    data = export_to_json_bytes(set())
    assert import_from_json_bytes(data) == set()

def test_import_collection_drops_unknown_codes():
    catalog = [PaintColor(name="Red", hex="#ff0000", code="72.112")]
    data = _json.dumps({"owned": ["72.112", "INVALID_CODE"]}).encode()
    result = import_from_json_bytes(data, catalog=catalog)
    assert result == {"72.112"}

def test_import_collection_no_catalog_returns_all_codes():
    data = _json.dumps({"owned": ["anything", "goes"]}).encode()
    result = import_from_json_bytes(data, catalog=None)
    assert result == {"anything", "goes"}

def test_export_produces_sorted_json():
    data = export_to_json_bytes({"b_code", "a_code"})
    parsed = _json.loads(data)
    assert parsed["owned"] == sorted(["b_code", "a_code"])
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv/Scripts/python -m pytest tests/test_collection.py -k "export or import" -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Refactor `load()` to extract `_validate_codes`, then add the two new functions**

In `src/mini_highlight_advisor/collection.py`, replace the `load` function and add the new functions:

```python
def _validate_codes(stored: set[str], catalog: list[PaintColor] | None) -> set[str]:
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
    return result


def load(path: Path = COLLECTION_PATH, catalog: list[PaintColor] | None = None) -> set[str]:
    path = Path(path)
    if not path.exists():
        return set()
    stored = set(json.loads(path.read_text(encoding="utf-8")).get("owned", []))
    return _validate_codes(stored, catalog)


def export_to_json_bytes(owned: set[str]) -> bytes:
    return json.dumps({"owned": sorted(owned)}, indent=2).encode("utf-8")


def import_from_json_bytes(data: bytes, catalog: list[PaintColor] | None = None) -> set[str]:
    stored = set(json.loads(data.decode("utf-8")).get("owned", []))
    return _validate_codes(stored, catalog)
```

- [ ] **Step 4: Run all collection tests**

```
.venv/Scripts/python -m pytest tests/test_collection.py -v
```

Expected: all PASS (including the pre-existing tests — `_validate_codes` refactor must not change `load()` behaviour).

- [ ] **Step 5: Commit**

```
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor add src/mini_highlight_advisor/collection.py tests/test_collection.py
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor commit -m "feat: add collection export/import core functions"
```

---

### Task 4: Collection export/import — UI

**Files:**
- Modify: `ui/paints_tab.py`
- Modify: `locales/en.json`
- Modify: `locales/es.json`

**Interfaces:**
- Consumes: `collection.export_to_json_bytes`, `collection.import_from_json_bytes` (Task 3)
- Consumes: `context.CATALOG`, `keys.OWNED` (already used in `paints_tab.py`)

- [ ] **Step 1: Add i18n keys**

In `locales/en.json`, inside the `"paints"` object, add:

```json
"manage_collection_expander": "Back up / restore",
"download_collection_btn": "⬇ Download my_paints.json",
"import_collection_label": "Import collection (.json)",
"collection_imported_toast": "Imported {count} paint(s)",
"import_collection_error": "Import failed: {err}"
```

In `locales/es.json`, inside the `"paints"` object, add:

```json
"manage_collection_expander": "Copia de seguridad / restaurar",
"download_collection_btn": "⬇ Descargar mis_pinturas.json",
"import_collection_label": "Importar colección (.json)",
"collection_imported_toast": "Se importaron {count} pintura(s)",
"import_collection_error": "Error al importar: {err}"
```

- [ ] **Step 2: Add `_render_collection_io` function and call it from `render()`**

Replace the entire contents of `ui/paints_tab.py` with:

```python
"""The '🎨 Paints' tab: owned-paint inventory."""
import streamlit as st

from mini_highlight_advisor import collection
from mini_highlight_advisor.catalog import find_by_code
from i18n import t
from ui import context, helpers, keys

_COLL_IMPORT_NONCE = "_coll_import_nonce"


def render() -> tuple[list[str], list]:
    st.markdown(t("paints.heading"))
    owned_codes = collection.load(catalog=context.CATALOG)
    picked = st.multiselect(
        t("paints.multiselect_label"), context.CATALOG_CODES,
        default=sorted(owned_codes & set(context.CATALOG_CODES)),
        format_func=lambda c: context.CODE_LABEL.get(c, c),
        key=keys.OWNED,
    )
    if set(picked) != owned_codes:
        collection.save(set(picked))
    owned_paints = [p for c in picked if (p := find_by_code(context.CATALOG, c)) is not None]

    st.markdown(t("paints.owned_heading"))
    if not owned_paints:
        st.caption(t("paints.no_paints_caption"))
    for p in owned_paints:
        rng = p.paint_range or ""
        st.markdown(f"{helpers.swatch(p.hex)}{p.name} · {rng} · {p.code}", unsafe_allow_html=True)

    st.caption(t("paints.catalogue_caption", count=len(context.CATALOG)))
    _render_collection_io(set(picked))
    return picked, owned_paints


def _render_collection_io(owned: set[str]) -> None:
    with st.expander(t("paints.manage_collection_expander")):
        if owned:
            st.download_button(
                t("paints.download_collection_btn"),
                data=collection.export_to_json_bytes(owned),
                file_name="my_paints.json",
                mime="application/json",
                key="_coll_dl_btn",
            )

        nonce = st.session_state.get(_COLL_IMPORT_NONCE, 0)
        uploader_key = f"_coll_import_{nonce}"

        def _on_import():
            uploaded = st.session_state.get(uploader_key)
            if uploaded is None:
                return
            try:
                imported = collection.import_from_json_bytes(
                    uploaded.read(), catalog=context.CATALOG
                )
                collection.save(imported)
                st.session_state[keys.OWNED] = sorted(imported)
                st.session_state[_COLL_IMPORT_NONCE] = nonce + 1
                st.session_state["_coll_import_count"] = len(imported)
            except Exception as exc:
                st.session_state["_coll_import_err"] = str(exc)

        st.file_uploader(
            t("paints.import_collection_label"),
            type=["json"],
            key=uploader_key,
            on_change=_on_import,
        )
        if count := st.session_state.pop("_coll_import_count", None):
            st.toast(t("paints.collection_imported_toast", count=count))
        if err := st.session_state.pop("_coll_import_err", None):
            st.error(t("paints.import_collection_error", err=err))
```

- [ ] **Step 3: Smoke-test manually**

Run `streamlit run app.py`, go to the Paints tab. Verify:
- "Back up / restore" expander appears at the bottom
- With paints selected, "Download my_paints.json" button appears and downloads a valid JSON file
- The import uploader appears

- [ ] **Step 4: Commit**

```
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor add ui/paints_tab.py locales/en.json locales/es.json
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor commit -m "feat: collection export/import UI in paints tab"
```

---

### Task 5: Extended built-in recipes

**Files:**
- Modify: `src/mini_highlight_advisor/data/recipes_builtin.json`

No code changes. No tests needed (the existing `test_load_builtin_has_nmm_copper_dark_to_light` still covers the loader; new content is validated by that same parse path).

- [ ] **Step 1: Replace recipes_builtin.json with an extended set**

Replace the full file contents with:

```json
{
  "recipes": [
    {
      "name": "NMM Copper",
      "steps": [
        {"label": "Shadow",         "hex": "#3D2A25", "paint_ref": "Charred Brown"},
        {"label": "Base",           "hex": "#A75A38", "paint_ref": "Orange Brown"},
        {"label": "Midtone",        "hex": "#E15E32", "paint_ref": "Bright Orange"},
        {"label": "Highlight",      "hex": "#EAA88C", "paint_ref": "Beige Red"},
        {"label": "Edge Highlight", "hex": "#F5F5F3", "paint_ref": "Off-White"}
      ]
    },
    {
      "name": "NMM Gold",
      "steps": [
        {"label": "Shadow",                "hex": "#3C2E2B", "paint_ref": "German Camouflage Black Brown"},
        {"label": "Deep Shadow",           "hex": "#B35928", "paint_ref": "Parasite Brown"},
        {"label": "Midtone",               "hex": "#FFCE00", "paint_ref": "Gold Yellow"},
        {"label": "Highlight",             "hex": "#EBE06E", "paint_ref": "Toxic Yellow"},
        {"label": "Extreme Edge Highlight","hex": "#F5F5F3", "paint_ref": "Off-White"}
      ]
    },
    {
      "name": "NMM Silver",
      "steps": [
        {"label": "Shadow",         "hex": "#1A1A2E", "paint_ref": "Dark Prussian Blue"},
        {"label": "Dark Metal",     "hex": "#404858", "paint_ref": "Dark Sea Blue"},
        {"label": "Midtone",        "hex": "#808898", "paint_ref": "London Grey"},
        {"label": "Highlight",      "hex": "#C8D0D8", "paint_ref": "Light Grey"},
        {"label": "Edge Highlight", "hex": "#F0F4F8", "paint_ref": "Off-White"}
      ]
    },
    {
      "name": "Power Armour Blue",
      "steps": [
        {"label": "Shadow",         "hex": "#0D1A3A", "paint_ref": "Dark Prussian Blue"},
        {"label": "Base",           "hex": "#1E4B87", "paint_ref": "Ultramarine Blue"},
        {"label": "Midtone",        "hex": "#3878B0", "paint_ref": "Royal Blue"},
        {"label": "Highlight",      "hex": "#6AA8D0", "paint_ref": "Sky Blue"},
        {"label": "Edge Highlight", "hex": "#B8D8F0", "paint_ref": "Ice Blue"}
      ]
    },
    {
      "name": "Power Armour Red",
      "steps": [
        {"label": "Shadow",         "hex": "#2A0808", "paint_ref": "Black Red"},
        {"label": "Base",           "hex": "#801A1A", "paint_ref": "Cavalry Brown"},
        {"label": "Midtone",        "hex": "#B01A1A", "paint_ref": "Flat Red"},
        {"label": "Highlight",      "hex": "#D44040", "paint_ref": "Scarlet"},
        {"label": "Edge Highlight", "hex": "#F08080", "paint_ref": "Salmon Rose"}
      ]
    },
    {
      "name": "Power Armour Green",
      "steps": [
        {"label": "Shadow",         "hex": "#0A1A0E", "paint_ref": "German Camouflage Black Brown"},
        {"label": "Base",           "hex": "#1A5828", "paint_ref": "Dark Green"},
        {"label": "Midtone",        "hex": "#3A8840", "paint_ref": "Bright Green"},
        {"label": "Highlight",      "hex": "#68B858", "paint_ref": "Yellow Green"},
        {"label": "Edge Highlight", "hex": "#A8E098", "paint_ref": "Lime Green"}
      ]
    },
    {
      "name": "Warm Skin",
      "steps": [
        {"label": "Shadow",         "hex": "#3D2010", "paint_ref": "Charred Brown"},
        {"label": "Base",           "hex": "#7A3820", "paint_ref": "Beige Brown"},
        {"label": "Midtone",        "hex": "#C87848", "paint_ref": "Flat Flesh"},
        {"label": "Highlight",      "hex": "#E8A878", "paint_ref": "Light Flesh"},
        {"label": "Edge Highlight", "hex": "#F8D8B8", "paint_ref": "Pale Flesh"}
      ]
    },
    {
      "name": "Leather Brown",
      "steps": [
        {"label": "Shadow",         "hex": "#1A0E0A", "paint_ref": "Charred Brown"},
        {"label": "Base",           "hex": "#4A2018", "paint_ref": "Saddle Brown"},
        {"label": "Midtone",        "hex": "#7A4028", "paint_ref": "Leather Brown"},
        {"label": "Highlight",      "hex": "#A06040", "paint_ref": "Light Brown"},
        {"label": "Edge Highlight", "hex": "#C89070", "paint_ref": "Beige Brown"}
      ]
    }
  ]
}
```

- [ ] **Step 2: Verify the recipes load cleanly**

```
.venv/Scripts/python -c "from mini_highlight_advisor.recipes import load_builtin; r = load_builtin(); print([x.name for x in r])"
```

Expected: prints a list of 8 recipe names including the new ones.

- [ ] **Step 3: Run the existing recipe tests**

```
.venv/Scripts/python -m pytest tests/test_recipes.py -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor add src/mini_highlight_advisor/data/recipes_builtin.json
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor commit -m "feat: extend built-in recipes to 8 curated entries"
```

---

### Task 6: Sample content discovery module

**Files:**
- Create: `src/mini_highlight_advisor/samples.py`
- Create: `src/mini_highlight_advisor/data/samples/photos/.gitkeep`
- Create: `src/mini_highlight_advisor/data/samples/projects/.gitkeep`
- Test: `tests/test_samples.py`

**Interfaces:**
- Produces: `list_photos() -> list[SamplePhoto]`
- Produces: `list_projects() -> list[SampleProject]`
- Produces: `SamplePhoto(name: str, path: Path)` dataclass
- Produces: `SampleProject(name: str, path: Path)` dataclass

- [ ] **Step 1: Write failing tests**

Create `tests/test_samples.py`:

```python
from pathlib import Path
import pytest
from mini_highlight_advisor.samples import list_photos, list_projects, SamplePhoto, SampleProject


def test_list_photos_empty_when_dir_absent(tmp_path, monkeypatch):
    monkeypatch.setattr("mini_highlight_advisor.samples._PHOTOS_DIR", tmp_path / "nope")
    assert list_photos() == []


def test_list_projects_empty_when_dir_absent(tmp_path, monkeypatch):
    monkeypatch.setattr("mini_highlight_advisor.samples._PROJECTS_DIR", tmp_path / "nope")
    assert list_projects() == []


def test_list_photos_returns_images_only(tmp_path, monkeypatch):
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "rat-ogre.jpg").write_bytes(b"fake")
    (photos / "ignored.txt").write_bytes(b"ignored")
    monkeypatch.setattr("mini_highlight_advisor.samples._PHOTOS_DIR", photos)
    result = list_photos()
    assert len(result) == 1
    assert isinstance(result[0], SamplePhoto)
    assert result[0].name == "Rat Ogre"
    assert result[0].path.name == "rat-ogre.jpg"


def test_list_projects_returns_json_only(tmp_path, monkeypatch):
    projs = tmp_path / "projects"
    projs.mkdir()
    (projs / "rat-ogre.json").write_text("{}")
    (projs / "ignored.txt").write_text("ignored")
    monkeypatch.setattr("mini_highlight_advisor.samples._PROJECTS_DIR", projs)
    result = list_projects()
    assert len(result) == 1
    assert isinstance(result[0], SampleProject)
    assert result[0].name == "Rat Ogre"


def test_list_photos_sorted_alphabetically(tmp_path, monkeypatch):
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "b-mini.png").write_bytes(b"")
    (photos / "a-mini.png").write_bytes(b"")
    monkeypatch.setattr("mini_highlight_advisor.samples._PHOTOS_DIR", photos)
    result = list_photos()
    assert result[0].name == "A Mini"
    assert result[1].name == "B Mini"


def test_list_photos_skips_gitkeep(tmp_path, monkeypatch):
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / ".gitkeep").write_bytes(b"")
    monkeypatch.setattr("mini_highlight_advisor.samples._PHOTOS_DIR", photos)
    assert list_photos() == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv/Scripts/python -m pytest tests/test_samples.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create the samples module**

Create `src/mini_highlight_advisor/samples.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_SAMPLES_DIR = Path(__file__).parent / "data" / "samples"
_PHOTOS_DIR = _SAMPLES_DIR / "photos"
_PROJECTS_DIR = _SAMPLES_DIR / "projects"
_PHOTO_EXTS = {".png", ".jpg", ".jpeg"}


@dataclass(frozen=True)
class SamplePhoto:
    name: str
    path: Path


@dataclass(frozen=True)
class SampleProject:
    name: str
    path: Path


def _stem_to_name(stem: str) -> str:
    return stem.replace("-", " ").replace("_", " ").title()


def list_photos() -> list[SamplePhoto]:
    if not _PHOTOS_DIR.exists():
        return []
    return [
        SamplePhoto(name=_stem_to_name(p.stem), path=p)
        for p in sorted(_PHOTOS_DIR.iterdir())
        if p.suffix.lower() in _PHOTO_EXTS
    ]


def list_projects() -> list[SampleProject]:
    if not _PROJECTS_DIR.exists():
        return []
    return [
        SampleProject(name=_stem_to_name(p.stem), path=p)
        for p in sorted(_PROJECTS_DIR.iterdir())
        if p.suffix.lower() == ".json"
    ]
```

- [ ] **Step 4: Create the sample directories**

```
mkdir -p C:\Users\ag\alvaro\git\mini-highlight-advisor\src\mini_highlight_advisor\data\samples\photos
mkdir -p C:\Users\ag\alvaro\git\mini-highlight-advisor\src\mini_highlight_advisor\data\samples\projects
```

Create `.gitkeep` files so the empty directories are tracked:

```
echo "" > C:\Users\ag\alvaro\git\mini-highlight-advisor\src\mini_highlight_advisor\data\samples\photos\.gitkeep
echo "" > C:\Users\ag\alvaro\git\mini-highlight-advisor\src\mini_highlight_advisor\data\samples\projects\.gitkeep
```

- [ ] **Step 5: Run tests**

```
.venv/Scripts/python -m pytest tests/test_samples.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor add src/mini_highlight_advisor/samples.py tests/test_samples.py src/mini_highlight_advisor/data/samples/
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor commit -m "feat: add samples discovery module and data/samples/ folders"
```

---

### Task 7: Sample photos UI

**Files:**
- Modify: `app.py`
- Modify: `locales/en.json`
- Modify: `locales/es.json`

**Interfaces:**
- Consumes: `samples.list_photos()`, `samples.SamplePhoto` (Task 6)
- Consumes: `projects.AngleData`, `new_book`, `state._current_settings`, `state.set_active_angle`, `state.seed_editor_from_angle`, `keys.ANGLES` (all already imported in `app.py`)

- [ ] **Step 1: Add i18n keys**

In `locales/en.json`, inside the `"app"` object, add:

```json
"sample_photos_header": "Or try with a sample photo",
"use_sample_btn": "Use"
```

In `locales/es.json`, inside the `"app"` object, add:

```json
"sample_photos_header": "O prueba con una foto de muestra",
"use_sample_btn": "Usar"
```

- [ ] **Step 2: Add `samples` import to `app.py`**

In `app.py`, find the existing imports block. Add after the `from mini_highlight_advisor import projects` line:

```python
from mini_highlight_advisor import projects, samples
```

(Replace the existing `from mini_highlight_advisor import projects` line.)

- [ ] **Step 3: Add sample photo picker in `app.py`**

In the `with tab_studio:` block, find the `if not angles:` section:

```python
        if not angles:
            uploaded = st.file_uploader(t("app.photo_uploader"), type=["png", "jpg", "jpeg"])
            if uploaded is None:
                st.info(t("app.upload_prompt"))
            else:
                ...
```

After `st.info(t("app.upload_prompt"))` and before the `else:`, add the sample picker:

```python
            if uploaded is None:
                st.info(t("app.upload_prompt"))
                _sample_photos = samples.list_photos()
                if _sample_photos:
                    st.caption(t("app.sample_photos_header"))
                    _cols = st.columns(min(len(_sample_photos), 4))
                    for _i, (_col, _sp) in enumerate(zip(_cols, _sample_photos)):
                        with _col:
                            st.caption(_sp.name)
                            if st.button(t("app.use_sample_btn"), key=f"_sample_photo_{_i}"):
                                _photo_bytes = _sp.path.read_bytes()
                                _a = projects.AngleData(
                                    label="angle 1",
                                    photo_bytes=_photo_bytes,
                                    photo_suffix=_sp.path.suffix,
                                    book=new_book(5),
                                    settings=state._current_settings(),
                                )
                                st.session_state[keys.ANGLES] = [_a]
                                state.set_active_angle(0)
                                state.seed_editor_from_angle(_a)
                                st.rerun()
            else:
```

- [ ] **Step 4: Place at least one sample photo in the folder**

Copy a miniature photo of your choice into:
`src/mini_highlight_advisor/data/samples/photos/`

Use a descriptive filename like `rat-ogre.jpg` (becomes "Rat Ogre" in the UI). The app reads it at runtime — no code change needed.

- [ ] **Step 5: Smoke-test manually**

Run `streamlit run app.py`. When no photo is uploaded:
- If sample photos exist: caption + "Use" buttons appear below the upload prompt
- Clicking "Use" loads the photo and enters the editor immediately

- [ ] **Step 6: Commit**

```
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor add app.py locales/en.json locales/es.json src/mini_highlight_advisor/data/samples/photos/
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor commit -m "feat: sample photo picker in Studio tab"
```

---

### Task 8: Sample projects UI

**Files:**
- Modify: `ui/projects_panel.py`
- Modify: `locales/en.json`
- Modify: `locales/es.json`

**Interfaces:**
- Consumes: `samples.list_projects()`, `samples.SampleProject` (Task 6)
- Consumes: `projects.project_from_json_bytes` (already imported in `projects_panel.py`)
- Consumes: `keys.ANGLES`, `keys.OWNED`, `keys.LOADED_NAME`, `keys.SCHEMES`, `state.set_active_angle`, `state.seed_editor_from_angle` (already used in `projects_panel.py`)

- [ ] **Step 1: Add i18n keys**

In `locales/en.json`, inside the `"projects"` object, add:

```json
"samples_header": "Sample projects",
"load_sample_btn": "Load"
```

In `locales/es.json`, inside the `"projects"` object, add:

```json
"samples_header": "Proyectos de muestra",
"load_sample_btn": "Cargar"
```

- [ ] **Step 2: Add `samples` import to `projects_panel.py`**

In `ui/projects_panel.py`, add to the import block:

```python
from mini_highlight_advisor import projects, samples
```

(Replace `from mini_highlight_advisor import projects`.)

- [ ] **Step 3: Add `_render_sample_projects()` and call it from `render_library()`**

Add the following function to `ui/projects_panel.py`:

```python
def _render_sample_projects() -> None:
    sample_projs = samples.list_projects()
    if not sample_projs:
        return
    st.caption(t("projects.samples_header"))
    for sp in sample_projs:
        if st.button(sp.name, key=f"_sample_proj_{sp.path.stem}"):
            try:
                lp = projects.project_from_json_bytes(sp.path.read_bytes())
            except Exception as e:
                st.error(t("projects.load_error", err=str(e)))
                return
            st.session_state[keys.ANGLES] = list(lp.angles)
            state.set_active_angle(lp.active_angle)
            st.session_state[keys.OWNED] = list(lp.paints_pool)
            st.session_state[keys.LOADED_NAME] = sp.name
            state.seed_editor_from_angle(lp.angles[lp.active_angle])
            st.session_state[keys.SCHEMES] = list(lp.schemes)
            st.rerun()
```

Then at the end of `render_library()`, before the closing of the `with st.expander(...)` block, add a call:

```python
def render_library() -> None:
    """Upload a previously downloaded project JSON to restore it."""
    with st.expander(t("projects.load_expander"), expanded=False):
        # ... existing upload code unchanged ...

        if err := st.session_state.pop(_UPLOAD_ERR, None):
            st.error(t("projects.load_error", err=err))

        _render_sample_projects()   # ← add this line
```

Also add the missing `state` import to `projects_panel.py`. Current imports are:
```python
from ui import keys, state
```
That import already exists — no change needed.

- [ ] **Step 4: Place at least one demo project in the folder**

Copy a saved project `.json` file (e.g. the rat-ogre project from Downloads) into:
`src/mini_highlight_advisor/data/samples/projects/rat-ogre.json`

The app reads it at runtime — no code change needed. Keep file size in mind: one project JSON is ~4–5 MB; commit only the projects you intend to ship as permanent demos.

- [ ] **Step 5: Smoke-test manually**

Run `streamlit run app.py`, open the "Load project" expander in Studio. Verify:
- Sample project button(s) appear below the file uploader
- Clicking a button loads the project and enters the editor

- [ ] **Step 6: Commit**

```
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor add ui/projects_panel.py locales/en.json locales/es.json src/mini_highlight_advisor/data/samples/projects/
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor commit -m "feat: sample project loader in projects panel"
```

---

## Self-Review

**Spec coverage:**
- ✅ Global built-in recipes (Task 5 — extended from 2 to 8)
- ✅ Sample photos in `data/samples/photos/` with UI picker (Tasks 6, 7)
- ✅ Demo projects in `data/samples/projects/` with UI loader (Tasks 6, 8)
- ✅ Recipe export/import so user data survives redeploy (Tasks 1, 2)
- ✅ Paint collection export/import so user data survives redeploy (Tasks 3, 4)
- ✅ Both languages (en + es) covered for all new UI strings
- ✅ Citadel paints — intentionally out of scope per conversation ("at some point, don't know best way")

**Placeholder scan:** No TBD, TODO, or placeholder steps found.

**Type consistency:**
- `export_to_json_bytes` / `import_from_json_bytes` names are identical in Task 1 (recipe) and Task 3 (collection) — intentional parallel naming, no cross-task collisions since they live in different modules.
- `SamplePhoto.path`, `SampleProject.path` used consistently as `Path` in Tasks 6, 7, 8.
- `state.seed_editor_from_angle` called identically in Tasks 7 and 8 (same signature as existing usage in `app.py` and `projects_panel.py`).
