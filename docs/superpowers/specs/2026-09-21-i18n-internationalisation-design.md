# i18n — Internationalisation Design

## Overview

Add a production-quality internationalisation (i18n) system to mini-highlight-advisor. The system must be framework-agnostic at its core so the translation infrastructure survives if the app ever moves away from Streamlit. Initial languages: English (en) and Spanish (es). Architecture supports adding further languages by dropping a new JSON catalog file — no code changes required.

---

## Goals

- All user-facing strings in `ui/` are translatable via a `t("key")` call
- Language is selected via a sidebar selectbox and persisted via `?lang=es` URL param
- Missing translations fall back to English silently — the app never crashes on a missing key
- `src/` (core logic) has zero knowledge of i18n — it remains pure Python
- Panel migration is incremental: untranslated panels stay in English until migrated

## Non-goals

- Paint name translation (Citadel/Vallejo product names stay as-is)
- Pluralisation rules or locale-aware number/date formatting
- Right-to-left language support

---

## Architecture

```
mini-highlight-advisor/
├── src/
│   └── i18n/
│       ├── __init__.py       ← public API: t(), set_lang(), available_langs()
│       ├── loader.py         ← loads and merges JSON catalogs from locales/
│       └── translator.py     ← key lookup, fallback logic, {placeholder} interpolation
│
├── locales/
│   ├── en.json               ← source of truth; always complete
│   └── es.json               ← partial is fine; gaps fall back to en.json
│
└── ui/
    └── lang.py               ← Streamlit adapter (only file that imports st + i18n together)
```

**Data flow:**

```
Browser URL  ?lang=es
                ↓
         ui/lang.py           reads st.query_params → set_lang("es") → st.session_state["lang"]
                ↓
         src/i18n/            t("colour_panel.bands_header", n=3)
         translator.py        → "es" catalog hit  → "3 capas (oscuro → claro)"
                              → "es" catalog miss → fallback to "en" → "3 bands (dark → light)"
                              → key not in either → return key string (never raises)
```

`src/i18n/` has **zero Streamlit imports**. Replacing the Streamlit adapter means rewriting `ui/lang.py` only.

---

## Catalog format

Nested JSON, namespaced by panel. `en.json` is the authoritative source. `es.json` is merged over `en.json` at `set_lang()` time — only keys that differ need to be present.

```json
// locales/en.json
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
  },
  "surface": {
    "skin": "Skin",
    "armour": "Armour",
    "cloth": "Cloth"
  },
  "colour_panel": {
    "expander_scheme": "Generate scheme (surfaces + hero colour + mood)",
    "caption_tag_regions": "Tag each region, then pick a hero colour and a mood.",
    "label_surface": "Surface — {name}",
    "label_hero_colour": "Hero colour",
    "checkbox_owned_only": "Owned only (no catalogue suggestions)",
    "button_generate": "✨ Generate & apply scheme",
    "ramp_standard": "Ramp",
    "ramp_complementary": "Complementary",
    "ramp_warm": "Warm (+30°)",
    "ramp_cool": "Cool (−30°)",
    "bands_header": "{n} bands (dark → light)"
  },
  "results": {
    "edge_highlights": "Edge highlights",
    "edge_sensitivity": "Edge sensitivity",
    "edge_sensitivity_help": "Few sharpest edges (left) to more edges (right).",
    "technique_label": "Technique — {region_name}",
    "subheader_osl": "Object-source glow — extra steps"
  }
}
```

```json
// locales/es.json (partial — only keys that differ from en.json)
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

**Key conventions:**
- Namespace = panel filename without `.py` (e.g. `colour_panel`, `results`, `osl_panel`)
- Dynamic values use `{placeholder}` — interpolated via `.format(**kwargs)` in `translator.py`
- Emoji live inside the catalog value, not in code — translators can keep or drop them per language
- Data-structure display strings (surface types, technique names, NMM presets) go under their own namespace (`surface.*`, `technique.*`, `nmm_preset.*`) — translated at the render site in `ui/`, never in `src/`

---

## Public API — `src/i18n/`

```python
def set_lang(lang: str) -> None:
    """Set active language. Loads and merges catalogs. Called once by ui/lang.py."""

def t(key: str, **kwargs) -> str:
    """
    Translate key in active language. Falls back to 'en'. Interpolates kwargs.

    t("colour_panel.bands_header", n=3)  →  "3 bands (dark → light)"
    t("nonexistent.key")                 →  "nonexistent.key"
    """

def available_langs() -> list[str]:
    """Return language codes with a catalog file on disk. e.g. ["en", "es"]"""
```

`translator.py` holds one merged dict per language built at `set_lang()` time. Lookup is a single dict access — no file I/O at render time.

---

## Streamlit adapter — `ui/lang.py`

```python
import streamlit as st
from i18n import set_lang, available_langs, t as _t

_LANG_LABELS = {
    "en": "🇬🇧 English",
    "es": "🇪🇸 Español",
}

def init_lang() -> None:
    """Call once at app startup, before any st.* calls."""
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
        format_func=lambda l: _LANG_LABELS.get(l, l),
    )
    if chosen != current:
        st.query_params["lang"] = chosen
        st.rerun()
```

**`app.py` changes — two lines only:**

```python
from ui.lang import init_lang, lang_selector

init_lang()      # first line of app, before any st.* call
lang_selector()  # after st.set_page_config, in sidebar block
```

---

## Migration plan

Migration is incremental. The infrastructure ships first; panels migrate one PR at a time. Untranslated panels remain in English — no crash, no visible gap to the user while `lang=en`.

### Phase 1 — Infrastructure (PR 1)

- `src/i18n/` module
- `locales/en.json` and `locales/es.json` (app-level keys only)
- `ui/lang.py`
- `app.py`: `init_lang()`, `lang_selector()`, tab names via `t()`
- Tests: fallback, interpolation, missing-key safety
- **No panel strings migrated yet**

### Phase 2 — Panel migration (one PR per batch)

| PR | Panels | Est. strings |
|----|--------|-------------|
| 2  | `colour_panel.py` | ~77 |
| 3  | `results.py` | ~45 |
| 4  | `osl_panel.py`, `regions_panel.py` | ~47 |
| 5  | `angles_panel.py`, `projects_panel.py`, `gallery_panel.py` | ~54 |
| 6  | remaining panels + `app.py` body strings | ~50 |

Each panel PR: extract strings → add to `en.json` → add to `es.json` → replace literals with `t()` calls. No other files touched.

### Data-structure display strings

`SURFACES[s].display`, `TechniqueSpec.name`, NMM preset names live in `src/` but render in `ui/`. Rule: **translate at the render site**.

```python
# ui/colour_panel.py — before
st.selectbox(f"Surface — {name}", surf_keys, format_func=lambda s: SURFACES[s].display)

# after
st.selectbox(t("colour_panel.label_surface", name=name), surf_keys,
             format_func=lambda s: t(f"surface.{s}"))
```

`src/` is never modified for i18n purposes.

---

## Testing

All tests in `tests/i18n/`. Pure Python — no Streamlit mocking required.

| Test | What it checks |
|------|----------------|
| `test_fallback_to_english` | key present in `en` but not `es` → returns English value |
| `test_missing_key_returns_key` | key absent from both catalogs → returns the key string |
| `test_interpolation` | `t("key", n=3)` → value with `{n}` replaced |
| `test_es_no_missing_keys` | every key in `en.json` exists in `es.json` (completeness gate) |
| `test_no_dead_keys` | every key in `en.json` is referenced in `ui/` (hygiene gate) |

The completeness and dead-key tests run in CI and fail loudly — they are the long-term maintenance guard that keeps the catalog honest as the app grows.

---

## Adding a new language

1. Copy `locales/es.json` → `locales/fr.json`
2. Translate values
3. `available_langs()` picks it up automatically — no code changes
4. `_LANG_LABELS` in `ui/lang.py` gets one new entry for the display label

---

## Open questions

None. Design is complete.
