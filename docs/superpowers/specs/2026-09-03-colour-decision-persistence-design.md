# Colour Decision Persistence + Cross-Region Seeding

**Date:** 2026-09-03  
**Status:** Draft

## Problem

The three colour levels (L1 scheme, L2 ramp, L3 bands) work well in isolation but don't
talk to each other or survive navigation. L3 palette slots are already persisted via
`RegionBook`. L1 and L2 inputs — the decisions that *produced* those palettes — vanish
the moment you leave the panel. Returning to L1 shows blank pickers; L2 has no memory of
which midtone or variant you chose; and no region can seed another's colour from a shared
hero.

## Goals

1. L1 (hero colour + mood) survives tab-switching and project save/load.
2. L2 (ramp midtone + variant) survives per-region; picking colours for one region does
   not affect another.
3. Returning to either level pre-fills the pickers from stored state.
4. Once a hero colour is set, L2 for any region can derive its starting midtone from the
   hero's complement with one click.
5. L3 shows full mix-recipe advice ("Mix 2:1 X + Y") when the user's collection can't
   match a band with a single paint.

## Non-goals

- Automatic re-generation when inputs change. Stored inputs are a memory aid; regeneration
  remains an explicit user action.
- Cross-angle colour sharing. Each `AngleData` owns its own decisions.
- L1 surface assignments — these are already stored on `Region.surface` / `RegionBook.whole_surface`.

## Schema changes (`regions.py`, `region_state.py`)

### `Region` — two new optional fields

```python
@dataclass
class Region:
    ...                                        # existing fields unchanged
    ramp_midtone: str | None = None            # hex used to generate the L2 ramp
    ramp_variant: str | None = None            # "standard" | "complementary" | "warm" | "cool"
```

### `RegionBook` — two new optional fields

```python
@dataclass
class RegionBook:
    ...                                        # existing fields unchanged
    hero_hex: str | None = None               # L1 hero colour
    mood: str | None = None                   # L1 mood variant name
```

All four fields default to `None`. No existing code breaks; no migration gate required.

## Manifest persistence (`projects.py`)

Bump `SCHEMA_VERSION` from 4 → 5. No migration gate needed (all new fields are optional).

### `_write_angle` additions

**Drawn regions** (`drawn` list entries):
```json
{ "ramp_midtone": "#a03020", "ramp_variant": "complementary" }
```
Both keys written unconditionally; `None` serialises as JSON `null`.

**Book `whole` entry** — no change (hero/mood are on the book, not the whole-mini region).

**Book root entry** — new `colour_context` key:
```json
"colour_context": { "hero_hex": "#c07040", "mood": "warm" }
```

### `_read_angle` additions

```python
# drawn regions
ramp_midtone=d.get("ramp_midtone"),
ramp_variant=d.get("ramp_variant"),

# book
colour_context = b.get("colour_context", {})
book = RegionBook(
    ...
    hero_hex=colour_context.get("hero_hex"),
    mood=colour_context.get("mood"),
)
```

`_read_angle` also used by the legacy single-angle path (`load_project` ≥ v3 fall-through
at line 228). Apply the same `.get()` defaults there.

## UI changes (`ui/colour_panel.py`)

### Level 1 — `_render_level1(book, ...)`

**On open:** read `book.hero_hex` and `book.mood` to set the default values of the hero
colour picker and mood selectbox respectively. If `None`, pickers behave as today (blank /
first option).

**On "Generate & Apply":** after the existing scheme-generation call, write back:
```python
book.hero_hex = chosen_hex
book.mood     = chosen_mood
```

### Level 2 — `_render_level2(book, sel, ...)`

**On open:** if the selected region has `ramp_midtone` set, use it as the default value of
the midtone colour picker. If `ramp_variant` is set, pre-select the matching variant radio.

**On "Apply":** after writing slots to session state, write back to the region:
```python
region.ramp_midtone = midtone_hex
region.ramp_variant = chosen_variant   # "standard" | "complementary" | "warm" | "cool"
```

**Cross-region shortcut:** when `book.hero_hex` is not `None`, render a one-line hint
above the midtone picker:

> ⊕ Complement of hero — `[swatch]` `#hex`  **[Use]**

Clicking **Use** writes `hue_rotate(book.hero_hex, 180)` into the midtone picker's
session-state key (same mechanism as the existing Apply path, but just the midtone field).
No auto-apply; the user still clicks Apply to commit the generated ramp.

The shortcut is shown for all regions (including whole-mini) whenever `book.hero_hex` is
set. There is no region-level suppression — using the complement of your hero on any
region is a valid choice.

### Level 3 — `_render_level3(book, sel, picked, ...)`

Replace `collection.nearest_paint(paint.rgb, context.CATALOG)` with
`matching.match(target_from_band(slot_hex, finish), owned=list(picked), catalog=context.CATALOG)`
where `finish` is `"metallic"` when the region's material is `"nmm"` and `"matte"` otherwise.
(`target_from_band` already accepts a finish argument — see `matching.py`.)

Display `result.phrase` (already human-readable: "Use X", "Closest: X — slightly cooler",
"Mix 2:1 X + Y (approx.)", "Can't match — buy Z"). The coloured swatch and ownership
badge remain alongside the phrase.

`target_from_band` already exists in `matching.py` and produces a finish-inferred `Target`
from a hex. `picked` (the owned-paint set) is threaded into Level 3 via the existing
`render(book, sel, picked, owned_paints)` signature.

## Testing

| Area | What to test |
|---|---|
| Schema | `_write_angle` → `_read_angle` round-trip preserves all four new fields, including `None` |
| Back-compat | Loading a v4 manifest produces `hero_hex=None`, `mood=None`, `ramp_midtone=None`, `ramp_variant=None` |
| L1 write-back | After scheme generation, `book.hero_hex` and `book.mood` are set to the chosen values |
| L2 write-back | After ramp apply, `region.ramp_midtone` and `region.ramp_variant` reflect the input |
| Complement shortcut | `hue_rotate(hero_hex, 180)` is the value injected; shortcut hidden when hero_hex is None |
| Complement shortcut always visible | Shortcut shown for all regions when hero_hex is set; hidden when hero_hex is None |
| Mix guide — exact | Owned paint ΔE ≤ 1 → phrase "Use X (code)." |
| Mix guide — close | ΔE ≤ 5 → phrase mentions deviation ("slightly cooler") |
| Mix guide — mix | No owned single close enough, but 2-paint combo ΔE ≤ 8 → "Mix 2:1 X + Y (approx.)" |
| Mix guide — unreachable | No owned paint or mix meets threshold → buy hint shown |

## Files touched

| File | Change |
|---|---|
| `src/mini_highlight_advisor/regions.py` | Add `ramp_midtone`, `ramp_variant` to `Region` |
| `src/mini_highlight_advisor/region_state.py` | Add `hero_hex`, `mood` to `RegionBook` |
| `src/mini_highlight_advisor/projects.py` | `SCHEMA_VERSION` 4→5; write/read new fields |
| `ui/colour_panel.py` | L1/L2 pre-fill + write-back; complement shortcut; L3 mix phrase |
| `tests/test_projects.py` | Round-trip + back-compat tests |
| `tests/test_ui_colour_panel.py` | L1/L2 write-back; shortcut render/suppress |
| `tests/test_matching.py` | Already covers match tiers; add phrase-format assertions if missing |
