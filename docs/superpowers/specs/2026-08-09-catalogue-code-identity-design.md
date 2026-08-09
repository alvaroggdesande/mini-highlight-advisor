# Catalogue code-identity, hex→nearest, colour-box fix — design

Date: 2026-08-09
Branch: `feat/own-palette-input` (continue here; not yet merged)

## Problem

The catalogue grew to ~180 Vallejo paints across Model Color + Game Color and
gained a `code` field (e.g. `70.950`, `72.001`). Three coupled issues block the
merge:

1. **Identity is `name`.** `find_by_name`, the `CATALOG_NAMES` list feeding the
   layer selectboxes and the "Paints you own" multiselect, and `collection.json`
   (owned paints stored **by name**) all key off `name`. The catalogue validator
   also *rejects duplicate names*. To avoid that crash, 7 names were mangled
   (`White (Dead White)`, `Royal Purple model`, `Leather Brown game`,
   `Black game color`, `Beige Brown game`, `Yellow Olive game`, `Khaki game`).
   Reverting them to true product names is impossible while name must be unique,
   because true names collide across ranges (Dead White, Royal Purple, Leather
   Brown, Yellow Olive, Khaki all exist in both ranges).

2. **No hex→paint bridge.** A custom-target slot lets the user pick a hex, but it
   stays an anonymous colour — the user never learns which real paint is closest.

3. **Colour box renders inconsistently.** Catalogue slots draw the box with a
   *disabled* `st.color_picker(value=paint.hex, key=f"view_hex_{i}")`. When a
   widget has both `value=` and a `key=` whose session-state already exists,
   Streamlit ignores `value=` and keeps the first value the key held — so
   changing a slot's paint leaves the box showing the previous paint's colour.
   Very dark hexes also look like an empty box on the dark theme. Together:
   "sometimes the colour shows, sometimes it doesn't".

## Decisions (agreed)

- **`code` is the identity key** everywhere. Names become free-form display text.
- **Hex → suggest nearest** catalogue paint (non-binding); the hex still drives
  the preview.
- **Revert the 7 mangled names** to true product names as part of this work.

## Design

### 1. Data model — `PaintColor.code`
Add `code: str` to `PaintColor` (`palette.py`). `DEFAULT_PALETTE` entries get
their real codes (`70.950, 70.995, 70.991, 70.990, 70.951`). `code` is the unique
key. Add `find_by_code(catalog, code) -> PaintColor | None`. Keep `find_by_name`
only for best-effort recipe `paint_ref` resolution.

### 2. Catalogue validation — `catalog.py`
- Per entry require `code`, `name`, `hex`; hex matches `#rrggbb`.
- **Uniqueness on `code`** (not name). Duplicate names are allowed. Error
  messages identify the offending `code` for actionable hand-edit fixes.
- `load_catalog` populates `PaintColor.code`.

### 3. Paints tab — search + inventory (`app.py`)
- "Paints you own" multiselect: `options = [p.code ...]`,
  `format_func=lambda c: "Name · Range · code"`. Streamlit filters on the
  formatted label, so typing a name, a range, or a **code** all match.
  Selection stores codes; `collection.save`/`load` operate on codes.
- "Owned paints" list shows the code: `<swatch> Beige Red · Model Color · 70.804`.

### 4. Miniature tab — colour box + hex→nearest (`app.py`)
- **Colour box fix:** for a catalogue slot, render the box as the same inline
  HTML `<span>` swatch used in the Paints tab (driven purely by `paint.hex` each
  rerun, no session key, `1px solid #888` border so dark colours stay visible).
  Custom slots keep a real, editable `st.color_picker`.
- Layer selectbox `options = [codes...] + [CUSTOM]`, `format_func` for display.
  Slot session keys hold codes (or the `CUSTOM` sentinel).
- **Hex → nearest (non-binding):** for a custom slot, show the closest catalogue
  paint by RGB distance — e.g. `Closest: Parasite Brown · Game Color · 72.042
  (⚠️ not owned)` — reusing the nearest logic generalised to nearest-in-catalogue.

### 5. Ownership migration — `collection.json`
Now stores codes. Rewrite the current 17-name file directly with codes:

```
Beige Red→70.804, Black→70.950, Bloody Red→72.010, Dark Green→72.028,
Flat Brown→70.984, Gold Yellow→72.007, Gunmetal Grey→70.863, Hot Orange→72.009,
Ice Yellow→70.858, Ivory→70.918, Khaki→70.988, Light Grey→70.990,
Neutral Grey→70.991, Parasite Brown→72.042, Scorpy Green→72.032,
Sick Green→72.029, Silver→70.997
```

`collection.load()` gets a backward-compat shim: an entry that is not a known
code but matches exactly one paint by name is mapped to that code; otherwise it
is dropped silently. (Requires `load` to see the catalogue, or a helper that
takes the catalogue — keep the seam thin.)

### 6. Recipes — best-effort, no schema change (out of scope)
Recipe `paint_ref` stays a **name** string. On Load, resolve name → catalogue
paint only when it matches exactly one paint; otherwise treat the step as a
custom target using the recipe's own hex. So `Bright Orange` / `Toxic Yellow`
(absent from the catalogue) render as custom with no crash. Migrating recipes to
reference codes is a separate future task.

### 7. Name revert — `vallejo_paints.json`
Revert the 7 mangled names in place:
`White (Dead White)→Dead White`, `Royal Purple model→Royal Purple`,
`Leather Brown game→Leather Brown`, `Black game color→Black`,
`Beige Brown game→Beige Brown`, `Yellow Olive game→Yellow Olive`,
`Khaki game→Khaki`. Codes and hexes unchanged.

## Testing
- `test_catalog.py`: code-uniqueness enforced; duplicate names now allowed;
  error message names the offending code; missing `code` rejected.
- `test_collection.py`: save/load round-trips codes; name→code shim maps a
  unique legacy name and drops an unresolvable one.
- New: nearest-in-catalogue returns the RGB-closest paint.
- Existing pipeline/overlay tests untouched.

## Out of scope
- Recipe schema migration to codes.
- Any change to the analysis pipeline, masking, banding, overlay.
- Multi-brand support beyond Vallejo.
