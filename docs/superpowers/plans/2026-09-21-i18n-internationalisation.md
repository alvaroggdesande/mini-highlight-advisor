# i18n — Internationalisation Implementation Plan (Phase 1: Infrastructure)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a framework-agnostic i18n core (`src/i18n/`) with English and Spanish catalogs for app-level strings, wired into Streamlit via `ui/lang.py` and `app.py`.

**Architecture:** Three-layer system — `src/i18n/` holds pure-Python loader + translator with module-level state; `locales/*.json` are the data source; `ui/lang.py` is the only file that touches both Streamlit and i18n. The Streamlit adapter is deliberately thin so swapping the UI framework means rewriting one file. Panel strings (colour_panel, results, etc.) are **not** migrated in this PR — that is Phases 2–6.

**Tech Stack:** Python 3.11, JSON stdlib, Streamlit `st.query_params` / `st.session_state` / `st.sidebar`.

**Spec:** `docs/superpowers/specs/2026-09-21-i18n-internationalisation-design.md`

## Global Constraints

- `src/` logic has zero Streamlit imports — only `ui/lang.py` bridges them
- Missing translation keys never raise; they return the key string
- `es.json` falls back to `en.json` for missing keys; `en.json` is always complete
- Phase 1 catalogs contain **app-level keys only** (`sidebar.*`, `app.*`) — all other namespaces are added in later PRs as panels are migrated
- Tab emoji stay in code, text goes in catalog (matches the spec's en.json example values: `"Studio"`, not `"🖌️ Studio"`)
- No Streamlit imports inside `src/i18n/`
- Feature branch + PR; never build on `main`

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `locales/en.json` | Create | Source-of-truth Phase 1 catalog |
| `locales/es.json` | Create | Partial Spanish Phase 1 catalog |
| `src/i18n/__init__.py` | Create | Public API re-export: `t`, `set_lang`, `available_langs` |
| `src/i18n/loader.py` | Create | File I/O: load JSON, list available langs |
| `src/i18n/translator.py` | Create | Module-level state, merge, flatten, lookup, interpolate |
| `tests/i18n/__init__.py` | Create | Empty — makes directory a package |
| `tests/i18n/test_i18n.py` | Create | All 5 tests (4 in Task 2, dead-key in Task 3) |
| `ui/lang.py` | Create | Streamlit adapter: `init_lang()`, `lang_selector()` |
| `app.py` | Modify | Wire `init_lang()`, `lang_selector()`, tab/title `t()` calls |

---

### Task 1: Locale catalog files

**Files:**
- Create: `locales/en.json`
- Create: `locales/es.json`

**Interfaces:**
- Produces: `locales/*.json` on disk — consumed by `src/i18n/loader.py` in Task 2

- [ ] **Step 1: Create `locales/en.json`**

  ```json
  {
    "sidebar": {
      "language": "Language"
    },
    "app": {
      "title": "Mini Highlight Advisor",
      "tab_studio": "Studio",
      "tab_paint": "Paint guide",
      "tab_paints": "Paint collection",
      "tab_angles": "All angles",
      "tab_capture": "Capture & help"
    }
  }
  ```

- [ ] **Step 2: Create `locales/es.json`**

  ```json
  {
    "sidebar": {
      "language": "Idioma"
    },
    "app": {
      "title": "Ayuda para pintar miniaturas",
      "tab_studio": "Estudio",
      "tab_paint": "Guía de pintura",
      "tab_paints": "Colección de pinturas",
      "tab_angles": "Todos los ángulos",
      "tab_capture": "Captura y ayuda"
    }
  }
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add locales/en.json locales/es.json
  git commit -m "feat(i18n): add Phase 1 locale catalogs (en + es, app-level keys)"
  ```

---

### Task 2: Core i18n module (TDD — behavioral + catalog tests)

**Files:**
- Create: `tests/i18n/__init__.py`
- Create: `tests/i18n/test_i18n.py`
- Create: `src/i18n/__init__.py`
- Create: `src/i18n/loader.py`
- Create: `src/i18n/translator.py`

**Interfaces:**
- Consumes: `locales/en.json`, `locales/es.json` from Task 1
- Produces:
  - `set_lang(lang: str, *, _locales_dir: Path | None = None) -> None`
  - `t(key: str, **kwargs) -> str`
  - `available_langs() -> list[str]`
  - `translator._reset() -> None` (for test isolation only)

- [ ] **Step 1: Create `tests/i18n/__init__.py`** (empty file)

- [ ] **Step 2: Write the failing tests**

  Create `tests/i18n/test_i18n.py`:

  ```python
  import json
  import re
  from pathlib import Path

  import pytest

  from i18n import t, set_lang, available_langs
  from i18n import translator as _tr


  @pytest.fixture(autouse=True)
  def reset_state():
      _tr._reset()
      yield
      _tr._reset()


  @pytest.fixture
  def tmp_locales(tmp_path):
      en = {
          "app": {"title": "Hello", "msg": "Count: {n}"},
          "only_english": {"value": "EN only"},
      }
      es = {
          "app": {"title": "Hola"},
          # "app.msg" absent → fallback to en
          # "only_english" absent → fallback to en
      }
      (tmp_path / "en.json").write_text(json.dumps(en), encoding="utf-8")
      (tmp_path / "es.json").write_text(json.dumps(es), encoding="utf-8")
      return tmp_path


  def test_fallback_to_english(tmp_locales):
      set_lang("es", _locales_dir=tmp_locales)
      assert t("only_english.value") == "EN only"


  def test_missing_key_returns_key(tmp_locales):
      set_lang("en", _locales_dir=tmp_locales)
      assert t("nonexistent.key") == "nonexistent.key"


  def test_interpolation(tmp_locales):
      set_lang("en", _locales_dir=tmp_locales)
      assert t("app.msg", n=3) == "Count: 3"


  def test_es_all_keys_accessible():
      """Every en.json key returns a non-key value when lang=es (fallback works)."""
      set_lang("es")
      locales = Path(__file__).parents[2] / "locales"
      en_keys = _flatten_keys(json.loads((locales / "en.json").read_text(encoding="utf-8")))
      for key in en_keys:
          result = t(key)
          assert result != key, f"t({key!r}) returned itself — fallback broken"


  def _flatten_keys(d: dict, prefix: str = "") -> list[str]:
      keys = []
      for k, v in d.items():
          full = f"{prefix}.{k}" if prefix else k
          if isinstance(v, dict):
              keys.extend(_flatten_keys(v, full))
          else:
              keys.append(full)
      return keys
  ```

- [ ] **Step 3: Run tests — expect ImportError (module doesn't exist yet)**

  ```
  .venv\Scripts\python -m pytest tests/i18n/test_i18n.py -v
  ```

  Expected: `ModuleNotFoundError: No module named 'i18n'`

- [ ] **Step 4: Create `src/i18n/__init__.py`** (empty for now — allows the import to partially resolve)

  ```python
  ```

  *(empty file)*

- [ ] **Step 5: Re-run tests — expect ImportError on specific names**

  ```
  .venv\Scripts\python -m pytest tests/i18n/test_i18n.py -v
  ```

  Expected: `ImportError: cannot import name 't' from 'i18n'`

- [ ] **Step 6: Create `src/i18n/loader.py`**

  ```python
  from __future__ import annotations
  import json
  from pathlib import Path

  _DEFAULT_LOCALES: Path = Path(__file__).parent.parent.parent / "locales"


  def load_catalog(lang: str, locales_dir: Path = _DEFAULT_LOCALES) -> dict:
      """Load raw JSON catalog for lang. Returns {} if the file does not exist."""
      path = locales_dir / f"{lang}.json"
      if not path.exists():
          return {}
      with path.open(encoding="utf-8") as f:
          return json.load(f)


  def list_langs(locales_dir: Path = _DEFAULT_LOCALES) -> list[str]:
      """Return sorted language codes that have a catalog file on disk."""
      if not locales_dir.exists():
          return []
      return sorted(p.stem for p in locales_dir.glob("*.json"))
  ```

- [ ] **Step 7: Create `src/i18n/translator.py`**

  ```python
  from __future__ import annotations
  from pathlib import Path
  from .loader import load_catalog, list_langs, _DEFAULT_LOCALES

  _flat: dict[str, str] = {}        # active merged catalog (dot-separated keys)
  _en_flat: dict[str, str] = {}     # English-only flat catalog (fallback)
  _active_lang: str = "en"
  _active_locales_dir: Path = _DEFAULT_LOCALES   # set on each set_lang() call


  def set_lang(lang: str, *, _locales_dir: Path | None = None) -> None:
      """Load and merge catalogs for lang. Call once per rerun from ui/lang.py.

      _locales_dir is for test isolation only — omit in production.
      """
      global _flat, _en_flat, _active_lang, _active_locales_dir
      _active_locales_dir = _locales_dir or _DEFAULT_LOCALES
      _active_lang = lang
      en_raw = load_catalog("en", _active_locales_dir)
      _en_flat = _flatten(en_raw)
      if lang == "en":
          _flat = _en_flat
      else:
          lang_raw = load_catalog(lang, _active_locales_dir)
          _flat = _flatten(_deep_merge(en_raw, lang_raw))


  def t(key: str, **kwargs) -> str:
      """Translate key in active language, fallback to en, then to key itself."""
      val = _flat.get(key) or _en_flat.get(key, key)
      if kwargs:
          try:
              val = val.format(**kwargs)
          except (KeyError, ValueError):
              pass
      return val


  def available_langs(locales_dir: Path | None = None) -> list[str]:
      return list_langs(locales_dir or _active_locales_dir)


  def _deep_merge(base: dict, override: dict) -> dict:
      result = dict(base)
      for k, v in override.items():
          if isinstance(v, dict) and isinstance(result.get(k), dict):
              result[k] = _deep_merge(result[k], v)
          else:
              result[k] = v
      return result


  def _flatten(d: dict, prefix: str = "") -> dict[str, str]:
      out: dict[str, str] = {}
      for k, v in d.items():
          key = f"{prefix}.{k}" if prefix else k
          if isinstance(v, dict):
              out.update(_flatten(v, key))
          else:
              out[key] = str(v)
      return out


  def _reset() -> None:
      """Reset all module state. For test isolation only."""
      global _flat, _en_flat, _active_lang, _active_locales_dir
      _flat = {}
      _en_flat = {}
      _active_lang = "en"
      _active_locales_dir = _DEFAULT_LOCALES
  ```

  > **Why `_active_locales_dir` not `_locales_dir`:** Python raises `SyntaxError: name '_locales_dir' is parameter and global` if a parameter and a `global` declaration share the same name inside a function. The module-level variable uses a distinct name (`_active_locales_dir`) to avoid this.

- [ ] **Step 8: Update `src/i18n/__init__.py` to export the public API**

  ```python
  from .translator import set_lang, t, available_langs

  __all__ = ["t", "set_lang", "available_langs"]
  ```

- [ ] **Step 9: Run tests — expect 4 passes (dead-key test not written yet)**

  ```
  .venv\Scripts\python -m pytest tests/i18n/test_i18n.py -v
  ```

  Expected: 4 PASSED. If any fail, debug before proceeding.

  Common failure modes:
  - `ModuleNotFoundError: No module named 'i18n'` → re-run `pip install -e .` from the project root in `.venv`
  - `test_es_all_keys_accessible` fails with "returned itself" → `_deep_merge` not picking up en.json values; check that `en_raw` is loaded before merging

- [ ] **Step 10: Commit**

  ```bash
  git add src/i18n/ tests/i18n/
  git commit -m "feat(i18n): core i18n module with fallback, interpolation, and catalog tests"
  ```

---

### Task 3: Streamlit adapter + app.py wiring + dead-key test

**Files:**
- Create: `ui/lang.py`
- Modify: `app.py` (lines 1–27)
- Modify: `tests/i18n/test_i18n.py` (add `test_no_dead_keys`)

**Interfaces:**
- Consumes: `t`, `set_lang`, `available_langs` from `src/i18n/__init__.py`
- Produces:
  - `ui.lang.init_lang() -> None` — call once at app startup
  - `ui.lang.lang_selector() -> None` — renders sidebar selectbox

- [ ] **Step 1: Write the failing dead-key test**

  Append to `tests/i18n/test_i18n.py`:

  ```python
  def test_no_dead_keys():
      """Every key in en.json is referenced in at least one t() call in ui/ or app.py."""
      locales = Path(__file__).parents[2] / "locales"
      root = Path(__file__).parents[2]
      en_keys = set(_flatten_keys(json.loads((locales / "en.json").read_text(encoding="utf-8"))))

      pattern = re.compile(r'\bt\("([^"]+)"')
      used: set[str] = set()
      for py in (root / "ui").rglob("*.py"):
          used.update(pattern.findall(py.read_text(encoding="utf-8")))
      used.update(pattern.findall((root / "app.py").read_text(encoding="utf-8")))

      dead = en_keys - used
      assert not dead, f"Dead keys in en.json not referenced in ui/ or app.py: {sorted(dead)}"
  ```

- [ ] **Step 2: Run tests — expect test_no_dead_keys to fail**

  ```
  .venv\Scripts\python -m pytest tests/i18n/test_i18n.py::test_no_dead_keys -v
  ```

  Expected: FAIL — dead keys listed include `sidebar.language`, `app.title`, `app.tab_*`

- [ ] **Step 3: Create `ui/lang.py`**

  ```python
  import streamlit as st
  from i18n import set_lang, available_langs, t as _t

  _LANG_LABELS = {
      "en": "🇬🇧 English",
      "es": "🇪🇸 Español",
  }


  def init_lang() -> None:
      """Call once at app startup, before any other st.* calls."""
      lang = st.query_params.get("lang", "en")
      if lang not in available_langs():
          lang = "en"
      st.session_state["lang"] = lang
      set_lang(lang)


  def lang_selector() -> None:
      """Render language selectbox in sidebar. Rewrites URL param and reruns on change."""
      langs = available_langs()
      current = st.session_state.get("lang", "en")
      chosen = st.sidebar.selectbox(
          _t("sidebar.language"),
          langs,
          index=langs.index(current),
          format_func=lambda lang: _LANG_LABELS.get(lang, lang),
      )
      if chosen != current:
          st.query_params["lang"] = chosen
          st.rerun()
  ```

- [ ] **Step 4: Wire `app.py`**

  The current `app.py` top is:

  ```python
  import os
  from pathlib import Path

  import streamlit as st

  from mini_highlight_advisor import projects
  from mini_highlight_advisor.region_state import RegionBook, new_book
  from ui import (
      angles_panel, editor, gallery_panel, helpers, keys,
      paints_tab, projects_panel, ps_mode, results, state, _profile,
  )

  _profile.rerun_start()
  st.set_page_config(page_title="Mini Highlight Advisor", layout="wide")
  st.title("Mini Highlight Advisor")
  ...
  tab_studio, tab_paint, tab_paints, tab_angles, tab_capture = st.tabs([
      "🖌️ Studio", "🪜 Paint", "🎨 Paints", "🖼️ All angles", "📷 Capture & help",
  ])
  ```

  Make these exact changes:

  **a) Add import** — after the existing `from ui import (...)` block, add:

  ```python
  from ui.lang import init_lang, lang_selector
  from i18n import t
  ```

  **b) Add `init_lang()` call** — insert immediately after `_profile.rerun_start()`:

  ```python
  _profile.rerun_start()
  init_lang()                                             # ← ADD this line
  st.set_page_config(page_title="Mini Highlight Advisor", layout="wide")
  ```

  **c) Add `lang_selector()` call** — insert after `st.set_page_config`, before `st.title`:

  ```python
  st.set_page_config(page_title="Mini Highlight Advisor", layout="wide")
  lang_selector()                                        # ← ADD this line
  st.title(t("app.title"))                              # ← REPLACE st.title("Mini Highlight Advisor")
  ```

  **d) Replace tab labels** — replace the `st.tabs(...)` call.
  Use `+` (not f-strings) so `t()` calls can use double quotes and the dead-key
  test regex `t("...")` matches them. Python 3.11 can't nest the same quote type
  inside an f-string, which would break `f"... {t("key")}"`.

  ```python
  tab_studio, tab_paint, tab_paints, tab_angles, tab_capture = st.tabs([
      "🖌️ " + t("app.tab_studio"),
      "🪜 " + t("app.tab_paint"),
      "🎨 " + t("app.tab_paints"),
      "🖼️ " + t("app.tab_angles"),
      "📷 " + t("app.tab_capture"),
  ])
  ```

- [ ] **Step 5: Run all i18n tests — expect 5 passes**

  ```
  .venv\Scripts\python -m pytest tests/i18n/ -v
  ```

  Expected: 5 PASSED.

  If `test_no_dead_keys` still fails, check that the `t("...")` regex in the test matches the exact quote style used in `app.py` and `ui/lang.py` (double-quotes only). The pattern `r'\bt\("([^"]+)"'` matches `t("key")` but not `t('key')`. Either use consistent double-quotes in app.py or update the regex to also match single-quotes: `r"""\bt\(["']([^"']+)["']"""`.

- [ ] **Step 6: Run full test suite to check for regressions**

  ```
  .venv\Scripts\python -m pytest --tb=short -q
  ```

  Expected: all existing tests pass; no new failures.

- [ ] **Step 7: Smoke test the app in browser**

  ```
  .venv\Scripts\streamlit run app.py
  ```

  Check:
  - App opens; sidebar shows "Language" / "🇬🇧 English" by default
  - Switching to Spanish changes the selectbox label to "Idioma", title to "Ayuda para pintar miniaturas", tab labels to Spanish
  - Refreshing the page with `?lang=es` in the URL starts in Spanish
  - Switching back to English works
  - All existing Studio/Paint/Paints/Angles/Capture tab functionality unchanged

- [ ] **Step 8: Commit**

  ```bash
  git add ui/lang.py app.py tests/i18n/test_i18n.py
  git commit -m "feat(i18n): Streamlit adapter, app.py wiring, dead-key test — Phase 1 complete"
  ```

---

## Phases 2–6: Panel Migration (separate PRs)

Each panel PR follows the same pattern. For each batch of panels:

1. Run `grep -n 'st\.' ui/<panel>.py` to enumerate translatable strings
2. Add those keys under the panel's namespace in `locales/en.json`
3. Add Spanish translations to `locales/es.json`
4. Replace string literals with `t("namespace.key")` at the call site
5. Run `pytest tests/i18n/` — `test_no_dead_keys` gates accidental key drift

**Panel batches (from spec):**

| PR | Panels | Est. strings |
|----|--------|--------------|
| 2 | `colour_panel.py` | ~77 |
| 3 | `results.py` | ~45 |
| 4 | `osl_panel.py`, `regions_panel.py` | ~47 |
| 5 | `angles_panel.py`, `projects_panel.py`, `gallery_panel.py` | ~54 |
| 6 | remaining panels + `app.py` body strings | ~50 |

Data-structure display strings (`SURFACES[s].display`, `TechniqueSpec.name`, NMM preset names) live in `src/` but render in `ui/`. Translate at the render site only — `src/` is never modified for i18n:

```python
# Before
st.selectbox(f"Surface — {name}", surf_keys, format_func=lambda s: SURFACES[s].display)

# After
st.selectbox(t("colour_panel.label_surface", name=name), surf_keys,
             format_func=lambda s: t(f"surface.{s}"))
```
