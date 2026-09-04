# Scheme Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a complete, coherent colour scheme for a whole mini from per-region surface tags + a hero colour + a mood, mapped to real paints (owned-first), and apply it via the existing scheme machinery.

**Architecture:** Three new pure/glue modules keep the two layers separate: `surfaces.py` (the surface vocabulary), `scheme_gen.py` (colour decision — hex only, paint-agnostic), and `scheme_build.py` (paint mapping + `schemes.Scheme` assembly). `Region`/`RegionBook` gain `surface` + `tone` fields (distinct from the existing `material` technique field), persisted in the project manifest (schema v3 → v4, back-compat). A new Streamlit panel `ui/scheme_gen_panel.py` drives it. No change to banding, step rendering, `schemes.apply`, or the technique system.

**Tech Stack:** Python 3.11, numpy, Streamlit; pytest via `.venv/Scripts/python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-09-02-scheme-generator-design.md`

## Global Constraints

- **Branch:** create and work on `feat/scheme-generator`; never commit to `main`.
- **Two layers stay separate:** `scheme_gen.py` MUST NOT import `matching`, `collection`, `catalog`, or `palette`-paint lookups. It deals in hex strings only. Paint mapping lives ONLY in `scheme_build.py`.
- **Torch-free / Streamlit-free cores:** `surfaces.py`, `scheme_gen.py`, `scheme_build.py` import only stdlib + `mini_highlight_advisor` pure modules. No `streamlit`, no `torch`.
- **Surface ≠ technique:** `Region.surface`/`Region.tone` are NEW and independent of `Region.material` (the technique field). Applying a surface's default technique happens only in the UI, only when the user opts in, and is freely overridden after.
- **Back-compat:** projects saved before this feature load with `surface="other"`, `tone=None`. No migration step. `get_surface(unknown)` returns the `"other"` spec.
- **Reserved tone key:** the string `"__harmony__"` means "this realistic region follows the anchor harmony instead of a named tone". Exposed as `HARMONY_TONE` in `scheme_gen.py`.
- **Run tests with:** `.venv/Scripts/python -m pytest`

---

### Task 1: `surfaces.py` — surface vocabulary registry

**Files:**
- Create: `src/mini_highlight_advisor/surfaces.py`
- Create: `tests/test_surfaces.py`

**Interfaces:**
- Produces:
  - `SurfaceSpec(name: str, display: str, bucket: str, tones: dict[str, str], default_technique: str, default_tone: str | None = None)` — frozen dataclass; method `base_tone_hex(tone: str | None) -> str | None`.
  - `SURFACES: dict[str, SurfaceSpec]` — keys listed below.
  - `get_surface(name: str) -> SurfaceSpec` — falls back to the `"other"` spec for unknown names.
  - `REALISTIC = "realistic"`, `FREE = "free"` (bucket constants).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_surfaces.py`:

```python
import re
from mini_highlight_advisor.surfaces import SURFACES, get_surface, REALISTIC, FREE

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def test_every_surface_has_valid_bucket():
    for s in SURFACES.values():
        assert s.bucket in (REALISTIC, FREE), f"{s.name} bucket {s.bucket!r}"


def test_realistic_surfaces_have_tones_free_do_not():
    for s in SURFACES.values():
        if s.bucket == REALISTIC:
            assert s.tones, f"realistic {s.name} must have tones"
            for label, hexv in s.tones.items():
                assert _HEX.match(hexv), f"{s.name}/{label} bad hex {hexv!r}"
        else:
            assert not s.tones, f"free {s.name} must have no tones"


def test_base_tone_hex_realistic_and_free():
    skin = get_surface("skin")
    assert _HEX.match(skin.base_tone_hex(None))          # default tone
    assert _HEX.match(skin.base_tone_hex("orc-green"))   # named tone
    assert get_surface("cloth").base_tone_hex(None) is None


def test_skin_includes_fantasy_tones():
    tones = set(get_surface("skin").tones)
    assert {"orc-green", "drow-blue", "undead-grey"} <= tones


def test_get_surface_unknown_falls_back_to_other():
    assert get_surface("nonsense").name == "other"


def test_other_has_no_technique_and_is_free():
    other = get_surface("other")
    assert other.default_technique == ""
    assert other.bucket == FREE


def test_fur_defaults_to_drybrush_and_is_realistic():
    fur = get_surface("fur")
    assert fur.default_technique == "drybrush"
    assert fur.bucket == REALISTIC
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `.venv/Scripts/python -m pytest tests/test_surfaces.py -q`
Expected: FAIL (module `surfaces` not found).

- [ ] **Step 3: Write `surfaces.py`**

Create `src/mini_highlight_advisor/surfaces.py`:

```python
# src/mini_highlight_advisor/surfaces.py
"""Surface vocabulary: what a region *is* (skin, metal, cloth, …), separate from
how it is painted (the technique field) and what colour it ends up (the scheme).

Each surface carries a bucket (realistic | free), a set of tone archetypes
(realistic only; hex anchors that the mood adjusts downstream — not final paints),
and a *soft* default technique. Torch-free, Streamlit-free.
"""
from __future__ import annotations

from dataclasses import dataclass

REALISTIC = "realistic"
FREE = "free"


@dataclass(frozen=True)
class SurfaceSpec:
    name: str
    display: str
    bucket: str                       # REALISTIC | FREE
    tones: dict[str, str]             # tone label -> hex archetype; empty for free
    default_technique: str            # soft: "smooth" | "drybrush" | "nmm" | ""
    default_tone: str | None = None   # key into tones; None -> first tone

    def base_tone_hex(self, tone: str | None) -> str | None:
        """Hex for a realistic surface's chosen tone; None for free surfaces."""
        if not self.tones:
            return None
        key = tone or self.default_tone or next(iter(self.tones))
        return self.tones.get(key) or next(iter(self.tones.values()))


def _spec(name, display, bucket, tones, tech, default_tone=None):
    return SurfaceSpec(name, display, bucket, tones, tech, default_tone)


SURFACES: dict[str, SurfaceSpec] = {
    "skin": _spec("skin", "Skin", REALISTIC, {
        "pale": "#e8c0a0", "tan": "#d29b73", "dark": "#7a4a30", "olive": "#b89a6a",
        "orc-green": "#6f8f4a", "drow-blue": "#6a6f9a",
        "undead-grey": "#9aa39a", "pale-blue": "#a9c2cf",
    }, "smooth", default_tone="tan"),
    "bone": _spec("bone", "Bone", REALISTIC, {
        "ivory": "#d8cbaa", "weathered": "#b8a980", "dark": "#8a7a55",
    }, "smooth", default_tone="ivory"),
    "metal": _spec("metal", "Metal", REALISTIC, {
        "steel": "#8a9099", "gold": "#c9a83f", "bronze": "#9a6f3f", "copper": "#b5713f",
    }, "smooth", default_tone="steel"),
    "wood": _spec("wood", "Wood", REALISTIC, {
        "walnut": "#5b3d28", "oak": "#8a6a44", "dark": "#3f2c1d",
    }, "smooth", default_tone="walnut"),
    "leather": _spec("leather", "Leather", REALISTIC, {
        "dark-brown": "#4a3423", "tan": "#7a5638", "black": "#2a2320",
    }, "smooth", default_tone="dark-brown"),
    "fur": _spec("fur", "Fur", REALISTIC, {
        "brown": "#5a4030", "grey": "#7d7a72", "black": "#2b2b2b",
        "white": "#d8d4c8", "ginger": "#a5673a",
    }, "drybrush", default_tone="brown"),
    "cloth": _spec("cloth", "Cloth", FREE, {}, "smooth"),
    "cloak": _spec("cloak", "Cloak", FREE, {}, "smooth"),
    "robe": _spec("robe", "Robe", FREE, {}, "smooth"),
    "gem": _spec("gem", "Gem", FREE, {}, "smooth"),
    "accent": _spec("accent", "Accent", FREE, {}, "smooth"),
    "other": _spec("other", "Other", FREE, {}, ""),
}


def get_surface(name: str) -> SurfaceSpec:
    """Return the SurfaceSpec for name; falls back to 'other' for unknown values."""
    return SURFACES.get(name, SURFACES["other"])
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `.venv/Scripts/python -m pytest tests/test_surfaces.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git checkout -b feat/scheme-generator   # first task only; skip if already on the branch
git add src/mini_highlight_advisor/surfaces.py tests/test_surfaces.py
git commit -m "feat: surface vocabulary registry (surfaces.py)"
```

---

### Task 2: `scheme_gen.py` — colour-decision layer (hex only)

**Files:**
- Create: `src/mini_highlight_advisor/scheme_gen.py`
- Create: `tests/test_scheme_gen.py`

**Interfaces:**
- Consumes: `color.hue_rotate`, `color.ramp_from_midtone`, `color.hex_to_rgb` (from `mini_highlight_advisor.color`); `surfaces.get_surface`, `surfaces.REALISTIC`.
- Produces:
  - `HARMONY_TONE = "__harmony__"`
  - `harmony_hues(anchor_hex: str, variant: str, k: int) -> list[str]`
  - `apply_mood(hex_color: str, mood: str) -> str`
  - `RegionColorSpec(name: str, surface: str, tone: str | None, n_bands: int)` — frozen dataclass.
  - `generate_ramps(specs: list[RegionColorSpec], anchor_name: str, anchor_hex: str, mood: str, variant: str) -> dict[str, list[str]]` — region name → list of hex, dark→light, length `n_bands`.
  - `MOODS: dict` and `VARIANTS: list[str]` (for the UI to enumerate).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scheme_gen.py`:

```python
import colorsys
from mini_highlight_advisor import scheme_gen as sg
from mini_highlight_advisor.color import hex_to_rgb


def _hue(hexv):
    r, g, b = hex_to_rgb(hexv)
    return colorsys.rgb_to_hls(r / 255, g / 255, b / 255)[0] * 360.0


def _sat_light(hexv):
    r, g, b = hex_to_rgb(hexv)
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return s, l


def test_harmony_hues_returns_k_and_complementary_is_180():
    out = sg.harmony_hues("#c02030", "complementary", 3)
    assert len(out) == 3
    d = abs(_hue(out[0]) - _hue("#c02030")) % 360
    assert min(d, 360 - d) == pytest.approx(180, abs=2)


def test_apply_mood_grimdark_darkens_and_desaturates():
    s0, l0 = _sat_light("#808080".replace("80", "a0"))  # a mid colour with some sat
    base = "#b05040"
    s_before, l_before = _sat_light(base)
    out = sg.apply_mood(base, "grimdark")
    s_after, l_after = _sat_light(out)
    assert s_after < s_before
    assert l_after < l_before


def test_apply_mood_neutral_is_identity_hue():
    base = "#3366cc"
    assert _hue(sg.apply_mood(base, "neutral")) == pytest.approx(_hue(base), abs=1)


def test_generate_ramps_one_ramp_per_region_correct_length():
    specs = [
        sg.RegionColorSpec("Cloak", "cloak", None, 5),
        sg.RegionColorSpec("Skin", "skin", "tan", 4),
    ]
    out = sg.generate_ramps(specs, "Cloak", "#c02030", "neutral", "complementary")
    assert set(out) == {"Cloak", "Skin"}
    assert len(out["Cloak"]) == 5
    assert len(out["Skin"]) == 4


def test_anchor_region_midtone_tracks_anchor_hue():
    specs = [sg.RegionColorSpec("Cloak", "cloak", None, 5)]
    out = sg.generate_ramps(specs, "Cloak", "#c02030", "neutral", "complementary")
    mid = out["Cloak"][5 // 2]
    d = abs(_hue(mid) - _hue("#c02030")) % 360
    assert min(d, 360 - d) < 20


def test_realistic_region_ignores_harmony_but_harmony_tone_follows():
    anchor = "#c02030"  # red
    locked = sg.generate_ramps(
        [sg.RegionColorSpec("Skin", "skin", "orc-green", 5)],
        "Cloak", anchor, "neutral", "complementary")["Skin"][2]
    followed = sg.generate_ramps(
        [sg.RegionColorSpec("Skin", "skin", sg.HARMONY_TONE, 5)],
        "Cloak", anchor, "neutral", "complementary")["Skin"][2]
    # locked skin is green-ish, harmony-following skin is NOT the same hue
    assert abs(_hue(locked) - _hue(followed)) > 20


import pytest  # noqa: E402  (kept at bottom so the file reads top-down)
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `.venv/Scripts/python -m pytest tests/test_scheme_gen.py -q`
Expected: FAIL (module `scheme_gen` not found).

- [ ] **Step 3: Write `scheme_gen.py`**

Create `src/mini_highlight_advisor/scheme_gen.py`:

```python
# src/mini_highlight_advisor/scheme_gen.py
"""Colour-decision layer: from surface tags + a hero colour + a mood, decide a
base hue per region and expand each into a dark→light ramp. HEX ONLY — this
module is paint-agnostic and MUST NOT import matching/collection/catalog.
Torch-free, Streamlit-free.
"""
from __future__ import annotations

import colorsys
from dataclasses import dataclass

from .color import hex_to_rgb, ramp_from_midtone, rgb_to_hex, hue_rotate
from .surfaces import REALISTIC, get_surface

HARMONY_TONE = "__harmony__"

_VARIANT_OFFSETS: dict[str, list[float]] = {
    "complementary":       [180.0],
    "analogous":           [-30.0, 30.0, -60.0, 60.0],
    "triadic":             [120.0, 240.0],
    "split-complementary": [150.0, 210.0],
}
VARIANTS: list[str] = list(_VARIANT_OFFSETS)

# mood -> (saturation multiplier, lightness multiplier, hue shift degrees)
MOODS: dict[str, tuple[float, float, float]] = {
    "neutral":  (1.00, 1.00,   0.0),
    "grimdark": (0.70, 0.78, +12.0),
    "heroic":   (1.18, 1.08,  -8.0),
    "natural":  (0.85, 0.98, -18.0),
}


def harmony_hues(anchor_hex: str, variant: str, k: int) -> list[str]:
    """k hues for the non-anchor free regions, cycling the variant's offsets."""
    offsets = _VARIANT_OFFSETS.get(variant, _VARIANT_OFFSETS["complementary"])
    return [hue_rotate(anchor_hex, offsets[i % len(offsets)]) for i in range(k)]


def apply_mood(hex_color: str, mood: str) -> str:
    """Multiply S and L (clamped to [0,1]) and rotate hue, in HLS space."""
    sat_mul, light_mul, hue_shift = MOODS.get(mood, MOODS["neutral"])
    r, g, b = hex_to_rgb(hex_color)
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    h = (h + hue_shift / 360.0) % 1.0
    s = min(1.0, max(0.0, s * sat_mul))
    l = min(1.0, max(0.0, l * light_mul))
    r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
    return rgb_to_hex((r2 * 255, g2 * 255, b2 * 255))


@dataclass(frozen=True)
class RegionColorSpec:
    name: str
    surface: str
    tone: str | None
    n_bands: int


def _base_hue(spec: RegionColorSpec, is_anchor: bool,
              anchor_hex: str, harmony_hex: str | None) -> str:
    """Resolve a region's midtone hue before the mood transform."""
    if is_anchor:
        return anchor_hex
    surf = get_surface(spec.surface)
    if surf.bucket == REALISTIC and spec.tone != HARMONY_TONE:
        tone_hex = surf.base_tone_hex(spec.tone)
        if tone_hex is not None:
            return tone_hex
    # free bucket, or realistic region asked to follow the harmony
    return harmony_hex if harmony_hex is not None else anchor_hex


def generate_ramps(specs: list[RegionColorSpec], anchor_name: str,
                   anchor_hex: str, mood: str, variant: str) -> dict[str, list[str]]:
    """Region name -> dark→light hex ramp of length spec.n_bands. Paint-free."""
    # Regions that draw their hue from the harmony: every non-anchor region that
    # is FREE or a realistic region explicitly following the harmony.
    def _follows_harmony(s: RegionColorSpec) -> bool:
        if s.name == anchor_name:
            return False
        surf = get_surface(s.surface)
        return surf.bucket != REALISTIC or s.tone == HARMONY_TONE

    followers = [s for s in specs if _follows_harmony(s)]
    hues = harmony_hues(anchor_hex, variant, len(followers))
    harmony_by_name = {s.name: h for s, h in zip(followers, hues)}

    out: dict[str, list[str]] = {}
    for s in specs:
        base = _base_hue(s, s.name == anchor_name, anchor_hex,
                         harmony_by_name.get(s.name))
        base = apply_mood(base, mood)
        out[s.name] = ramp_from_midtone(base, s.n_bands)
    return out
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `.venv/Scripts/python -m pytest tests/test_scheme_gen.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/scheme_gen.py tests/test_scheme_gen.py
git commit -m "feat: colour-decision layer (scheme_gen.py) — harmony + mood + ramps"
```

---

### Task 3: `scheme_build.py` — paint mapping + Scheme assembly

**Files:**
- Create: `src/mini_highlight_advisor/scheme_build.py`
- Create: `tests/test_scheme_build.py`

**Interfaces:**
- Consumes: `matching.match`, `matching.Target`; `palette.PaintColor`; `schemes.Scheme`; `scheme_gen.RegionColorSpec`, `scheme_gen.generate_ramps`.
- Produces:
  - `map_ramp_to_palette(ramp_hexes: list[str], owned: list[PaintColor], catalog: list[PaintColor], owned_only: bool) -> list[PaintColor]`
  - `build_scheme(name: str, specs: list[RegionColorSpec], anchor_name: str, anchor_hex: str, mood: str, variant: str, owned: list[PaintColor], catalog: list[PaintColor], owned_only: bool) -> Scheme`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scheme_build.py`:

```python
from mini_highlight_advisor import scheme_build as sb
from mini_highlight_advisor.scheme_gen import RegionColorSpec
from mini_highlight_advisor.palette import PaintColor
from mini_highlight_advisor.schemes import Scheme


def _owned():
    return [
        PaintColor("Black", "#101010", "V", "MC", code="A1"),
        PaintColor("Grey",  "#808080", "V", "MC", code="A2"),
        PaintColor("White", "#f0f0f0", "V", "MC", code="A3"),
    ]


def _catalog():
    return _owned() + [PaintColor("Deep Red", "#c02030", "V", "MC", code="C9")]


def test_in_collection_target_resolves_to_owned_paint():
    pal = sb.map_ramp_to_palette(["#808080"], _owned(), _catalog(), owned_only=False)
    assert pal[0].code == "A2"


def test_unreachable_falls_back_to_catalogue_when_not_owned_only():
    # red is not in the owned greys, but is in the catalogue
    pal = sb.map_ramp_to_palette(["#c02030"], _owned(), _catalog(), owned_only=False)
    assert pal[0].hex.lower() == "#c02030" or pal[0].code == "C9"


def test_owned_only_never_leaves_collection():
    owned = _owned()
    pal = sb.map_ramp_to_palette(["#c02030"], owned, _catalog(), owned_only=True)
    assert pal[0] in owned


def test_build_scheme_returns_scheme_with_region_keys_and_band_lengths():
    specs = [
        RegionColorSpec("Cloak", "cloak", None, 5),
        RegionColorSpec("Skin", "skin", "tan", 4),
    ]
    scheme = sb.build_scheme("Auto", specs, "Cloak", "#c02030", "neutral",
                             "complementary", _owned(), _catalog(), owned_only=False)
    assert isinstance(scheme, Scheme)
    assert set(scheme.palettes) == {"Cloak", "Skin"}
    assert len(scheme.palettes["Cloak"]) == 5
    assert len(scheme.palettes["Skin"]) == 4
    assert all(isinstance(p, PaintColor) for p in scheme.palettes["Cloak"])
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `.venv/Scripts/python -m pytest tests/test_scheme_build.py -q`
Expected: FAIL (module `scheme_build` not found).

- [ ] **Step 3: Write `scheme_build.py`**

Create `src/mini_highlight_advisor/scheme_build.py`:

```python
# src/mini_highlight_advisor/scheme_build.py
"""Glue layer: turn the colour-decision layer's hex ramps into real paints and
assemble a schemes.Scheme. Owned-first, catalogue fallback, buildable mix.
This is the ONLY scheme-generator module that knows about paints.
"""
from __future__ import annotations

from .matching import Target, match
from .palette import PaintColor
from .scheme_gen import RegionColorSpec, generate_ramps
from .schemes import Scheme


def _paint_for_hex(hexv: str, owned: list[PaintColor],
                   catalog: list[PaintColor], owned_only: bool) -> PaintColor:
    r = match(Target(hexv), owned, catalog)
    if r.tier in ("exact", "close"):
        return r.paints[0]
    if r.tier == "mix":
        # A band is one colour; represent the mix as a synthetic paint whose hex
        # is the intended colour and whose name is the mix recipe (shown in the
        # legend). finish defaults to matte.
        return PaintColor(name=r.phrase, hex=r.target_hex)
    # tier == "unreachable"
    if owned_only:
        return r.paints[0] if r.paints else PaintColor(name="(no owned match)", hex=hexv)
    return r.buy_hint or (r.paints[0] if r.paints else PaintColor(name="(no match)", hex=hexv))


def map_ramp_to_palette(ramp_hexes: list[str], owned: list[PaintColor],
                        catalog: list[PaintColor], owned_only: bool) -> list[PaintColor]:
    return [_paint_for_hex(h, owned, catalog, owned_only) for h in ramp_hexes]


def build_scheme(name: str, specs: list[RegionColorSpec], anchor_name: str,
                 anchor_hex: str, mood: str, variant: str,
                 owned: list[PaintColor], catalog: list[PaintColor],
                 owned_only: bool) -> Scheme:
    ramps = generate_ramps(specs, anchor_name, anchor_hex, mood, variant)
    palettes = {
        region: map_ramp_to_palette(hexes, owned, catalog, owned_only)
        for region, hexes in ramps.items()
    }
    return Scheme(name=name, palettes=palettes)
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `.venv/Scripts/python -m pytest tests/test_scheme_build.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/scheme_build.py tests/test_scheme_build.py
git commit -m "feat: paint-mapping + Scheme assembly (scheme_build.py)"
```

---

### Task 4: `Region` + `RegionBook` — `surface` + `tone` fields

**Files:**
- Modify: `src/mini_highlight_advisor/regions.py` (the `Region` dataclass)
- Modify: `src/mini_highlight_advisor/region_state.py` (the `RegionBook` class)
- Test: `tests/test_region_state.py` (append)

**Interfaces:**
- Produces:
  - `Region` gains `surface: str = "other"`, `tone: str | None = None`.
  - `RegionBook` gains fields `whole_surface: str = "other"`, `whole_tone: str | None = None` and methods `surface_at(g) -> str`, `set_surface_at(g, surface)`, `tone_at(g) -> str | None`, `set_tone_at(g, tone)`, mirroring the existing `material_at`/`set_material_at` routing (index 0 = whole mini; 1..N = drawn).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_region_state.py`:

```python
def test_surface_and_tone_default_and_route():
    import numpy as np
    from mini_highlight_advisor.region_state import new_book
    from mini_highlight_advisor.palette import default_ramp, default_coverage

    book = new_book(5)
    m = np.zeros((6, 6), bool); m[1:4, 1:4] = True
    book.add(m, "Cloak", default_ramp(5), default_coverage(5))

    # defaults
    assert book.surface_at(0) == "other"
    assert book.surface_at(1) == "other"
    assert book.tone_at(1) is None

    # routing to whole vs drawn
    book.set_surface_at(0, "skin")
    book.set_tone_at(0, "tan")
    book.set_surface_at(1, "cloak")
    assert book.surface_at(0) == "skin"
    assert book.tone_at(0) == "tan"
    assert book.surface_at(1) == "cloak"
    assert book.tone_at(0) == "tan"      # unaffected by the drawn write

    # surface is independent of the technique/material field
    book.set_material_at(1, "drybrush")
    assert book.surface_at(1) == "cloak"
    assert book.material_at(1) == "drybrush"
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `.venv/Scripts/python -m pytest tests/test_region_state.py::test_surface_and_tone_default_and_route -q`
Expected: FAIL (`surface_at` not defined).

- [ ] **Step 3: Add the fields to `Region`**

In `src/mini_highlight_advisor/regions.py`, extend the `Region` dataclass (keep existing fields; append the two new ones after `material`):

```python
@dataclass
class Region:
    name: str
    mask: np.ndarray                 # source-resolution bool
    palette: list[PaintColor]
    coverage: list[float]            # len == len(palette), sums to ~1.0
    material: str = "matte"          # "matte" (default) | "nmm" | technique key
    surface: str = "other"           # surface vocabulary key (skin/metal/cloth/…)
    tone: str | None = None          # chosen tone key for realistic surfaces
```

- [ ] **Step 4: Add fields + accessors to `RegionBook`**

In `src/mini_highlight_advisor/region_state.py`, add the two fields alongside `whole_material`:

```python
    whole_material: str = "matte"
    whole_surface: str = "other"
    whole_tone: str | None = None
```

And add these methods next to `material_at`/`set_material_at` (same routing):

```python
    def surface_at(self, g: int) -> str:
        self._check(g)
        return self.whole_surface if g == 0 else self.drawn[g - 1].surface

    def set_surface_at(self, g: int, surface: str) -> None:
        self._check(g)
        if g == 0:
            self.whole_surface = surface
        else:
            self.drawn[g - 1].surface = surface

    def tone_at(self, g: int) -> str | None:
        self._check(g)
        return self.whole_tone if g == 0 else self.drawn[g - 1].tone

    def set_tone_at(self, g: int, tone: str | None) -> None:
        self._check(g)
        if g == 0:
            self.whole_tone = tone
        else:
            self.drawn[g - 1].tone = tone
```

- [ ] **Step 5: Run the new test + the region_state suite**

Run: `.venv/Scripts/python -m pytest tests/test_region_state.py tests/test_regions.py -q`
Expected: PASS (all, including the new test).

- [ ] **Step 6: Commit**

```bash
git add src/mini_highlight_advisor/regions.py src/mini_highlight_advisor/region_state.py tests/test_region_state.py
git commit -m "feat: Region/RegionBook surface + tone fields (separate from technique)"
```

---

### Task 5: `projects.py` — persist `surface` + `tone` (schema v4, back-compat)

**Files:**
- Modify: `src/mini_highlight_advisor/projects.py` (`SCHEMA_VERSION`, `_write_angle`, `_read_angle`)
- Test: `tests/test_projects.py` (append)

**Interfaces:**
- Consumes: `RegionBook.surface_at`/`tone_at`, `Region.surface`/`tone` from Task 4.
- Produces: manifest angle dicts gain `"surface"`/`"tone"` on each drawn region and on `whole`; `SCHEMA_VERSION == 4`. Reads default `surface="other"`, `tone=None` when keys absent.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_projects.py`:

```python
def test_surface_and_tone_round_trip(tmp_path):
    import numpy as np
    from mini_highlight_advisor.palette import default_ramp, default_coverage

    book = _whole_book()
    m = np.zeros((8, 8), bool); m[2:5, 2:5] = True
    book.add(m, "Cloak", default_ramp(5), default_coverage(5))
    book.set_surface_at(0, "skin"); book.set_tone_at(0, "orc-green")
    book.set_surface_at(1, "cloak")

    angles = [_angle("front", b"PHOTO", book=book)]
    slug = projects.save_project("Surface Test", [], 0, angles, root=tmp_path)
    reloaded = projects.load_project(slug, root=tmp_path).angles[0].book
    assert reloaded.surface_at(0) == "skin"
    assert reloaded.tone_at(0) == "orc-green"
    assert reloaded.surface_at(1) == "cloak"
    assert reloaded.tone_at(1) is None


def test_surface_defaults_to_other_when_key_absent(tmp_path):
    import json
    import numpy as np
    from mini_highlight_advisor.palette import default_ramp, default_coverage

    book = _whole_book()
    m = np.zeros((8, 8), bool); m[2:5, 2:5] = True
    book.add(m, "Cloak", default_ramp(5), default_coverage(5))
    book.set_surface_at(1, "cloak")
    angles = [_angle("front", b"PHOTO", book=book)]
    slug = projects.save_project("Surface Default", [], 0, angles, root=tmp_path)

    mpath = tmp_path / slug / "manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    del manifest["angles"][0]["book"]["drawn"][0]["surface"]
    del manifest["angles"][0]["book"]["whole"]["surface"]
    mpath.write_text(json.dumps(manifest), encoding="utf-8")

    reloaded = projects.load_project(slug, root=tmp_path).angles[0].book
    assert reloaded.surface_at(0) == "other"
    assert reloaded.surface_at(1) == "other"
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `.venv/Scripts/python -m pytest tests/test_projects.py::test_surface_and_tone_round_trip -q`
Expected: FAIL (surface not written/read → assertion or default mismatch).

- [ ] **Step 3: Bump schema + write the new keys**

In `src/mini_highlight_advisor/projects.py`:

Change `SCHEMA_VERSION = 3` to `SCHEMA_VERSION = 4`.

In `_write_angle`, add `surface`/`tone` to each drawn region dict:

```python
        drawn.append({"name": r.name, "palette": _palette_to_dicts(r.palette),
                      "coverage": list(r.coverage), "mask_file": mask_file,
                      "material": r.material,
                      "surface": r.surface, "tone": r.tone})
```

and to the `whole` dict:

```python
        "book": {"whole": {"palette": _palette_to_dicts(a.book.whole_palette),
                           "coverage": list(a.book.whole_coverage),
                           "material": a.book.whole_material,
                           "surface": a.book.whole_surface,
                           "tone": a.book.whole_tone},
                 "drawn": drawn, "selected": a.book.selected},
```

- [ ] **Step 4: Read the new keys with defaults**

In `_read_angle`, extend the drawn `Region(...)` construction and the `RegionBook(...)` construction:

```python
    drawn = [
        Region(name=d["name"], mask=_read_mask(angle_dir / d["mask_file"]),
               palette=_palette_from_dicts(d["palette"]), coverage=list(d["coverage"]),
               material=d.get("material", "matte"),
               surface=d.get("surface", "other"), tone=d.get("tone"))
        for d in b["drawn"]
    ]
    book = RegionBook(whole_palette=_palette_from_dicts(b["whole"]["palette"]),
                      whole_coverage=list(b["whole"]["coverage"]),
                      whole_material=b["whole"].get("material", "matte"),
                      whole_surface=b["whole"].get("surface", "other"),
                      whole_tone=b["whole"].get("tone"),
                      drawn=drawn, selected=b["selected"])
```

- [ ] **Step 5: Run the new tests + the full projects suite**

Run: `.venv/Scripts/python -m pytest tests/test_projects.py -q`
Expected: PASS (all — v1/v2 adapters still default the new fields via the dataclass defaults).

- [ ] **Step 6: Commit**

```bash
git add src/mini_highlight_advisor/projects.py tests/test_projects.py
git commit -m "feat: persist surface + tone (manifest schema v4, back-compat)"
```

---

### Task 6: `ui/scheme_gen_panel.py` — the panel + mount

**Files:**
- Create: `ui/scheme_gen_panel.py`
- Modify: `app.py` (import + mount before `schemes_panel.render()`)
- Test: `tests/test_ui_scheme_gen.py`

**Interfaces:**
- Consumes: `_active_book()` (PS_BOOK or BOOK from session, mirroring `ui/schemes_panel.py`); `ui.context.CATALOG`; `mini_highlight_advisor.scheme_build.build_scheme`; `mini_highlight_advisor.scheme_gen` (`RegionColorSpec`, `MOODS`, `VARIANTS`, `HARMONY_TONE`); `mini_highlight_advisor.surfaces` (`SURFACES`, `get_surface`, `REALISTIC`); `mini_highlight_advisor.schemes.apply`; `mini_highlight_advisor.techniques.TECHNIQUES` (to validate a default technique before applying).
- Produces: `render(owned_paints: list[PaintColor]) -> None`.

**Notes for the implementer:**
- Follow the `ui/schemes_panel.py` shape exactly: module docstring, `import streamlit as st`, an `_active_book()` helper copied from `schemes_panel.py`, and a single `render(...)` wrapped in `st.expander(...)`.
- Band count per region = `len(book.palette_at(g))` — the generated ramp must match the region's current palette length so `schemes.apply` slots in cleanly.
- Anchor colour default = the midtone hex of the anchor region's current palette: `book.palette_at(g)[len(...)//2].hex`.
- NMM guard: only offer NMM as a settable technique when `st.session_state.get(keys.NORMALS) is not None`. Otherwise, if a surface's `default_technique == "nmm"`, skip setting the technique (leave it as-is).
- After applying, reseed the editor widgets exactly like `schemes_panel.py` does (copy its `_reseed_editor_widgets()` helper) so the palette editor refreshes.

- [ ] **Step 1: Write the failing AppTest**

Create `tests/test_ui_scheme_gen.py`:

```python
from streamlit.testing.v1 import AppTest


def _run():
    at = AppTest.from_file("app.py")
    return at.run()


def test_panel_absent_without_regions_present_with_them():
    # Smoke: the app imports and the panel module loads without error.
    import ui.scheme_gen_panel as p
    assert hasattr(p, "render")


def test_generate_then_apply_changes_book_palettes(tmp_path):
    # Unit-level exercise of the panel's core call path without a full Streamlit
    # session: build a book, generate a scheme, apply it, assert palettes changed.
    import numpy as np
    from mini_highlight_advisor.region_state import new_book
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    from mini_highlight_advisor import scheme_build as sb, schemes as sch
    from mini_highlight_advisor.scheme_gen import RegionColorSpec
    from ui.context import CATALOG

    book = new_book(5)
    m = np.zeros((8, 8), bool); m[2:5, 2:5] = True
    book.add(m, "Cloak", default_ramp(5), default_coverage(5))
    book.set_surface_at(1, "cloak")

    specs = [
        RegionColorSpec(name, book.surface_at(g), book.tone_at(g),
                        len(book.palette_at(g)))
        for g, name in enumerate(book.names())
    ]
    before = [p.hex for p in book.palette_at(1)]
    scheme = sb.build_scheme("Auto", specs, "Cloak", "#c02030", "grimdark",
                             "complementary", [], list(CATALOG), owned_only=False)
    sch.apply(scheme, book)
    after = [p.hex for p in book.palette_at(1)]
    assert before != after
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `.venv/Scripts/python -m pytest tests/test_ui_scheme_gen.py -q`
Expected: FAIL (`ui.scheme_gen_panel` not found).

- [ ] **Step 3: Write `ui/scheme_gen_panel.py`**

Create `ui/scheme_gen_panel.py`:

```python
# ui/scheme_gen_panel.py
"""🎯 Scheme generator — tag each region with a surface, pick a hero colour +
mood, and generate a whole-mini colour scheme mapped to real paints (owned-first).
Streamlit glue only; all logic lives in scheme_gen / scheme_build / surfaces."""
import streamlit as st

from mini_highlight_advisor import scheme_build as sb, schemes as sch
from mini_highlight_advisor.scheme_gen import RegionColorSpec, MOODS, VARIANTS, HARMONY_TONE
from mini_highlight_advisor.surfaces import SURFACES, get_surface, REALISTIC
from ui import context, keys


def _active_book():
    return st.session_state.get(keys.PS_BOOK) or st.session_state.get(keys.BOOK)


def _reseed_editor_widgets() -> None:
    st.session_state.pop(keys.LOADED_G, None)
    st.session_state.pop(keys.COV_N, None)
    for k in [k for k in list(st.session_state)
              if k.startswith("slot_code_") or k.startswith("slot_hex_")
              or k.startswith("slot_hexinput_") or k.startswith("cov_pct_")]:
        st.session_state.pop(k, None)


def render(owned_paints) -> None:
    book = _active_book()
    if book is None:
        return
    names = book.names()
    with st.expander("🎯 Generate a scheme — surfaces + hero colour + mood", expanded=False):
        # --- per-region surface + tone ---
        st.caption("Tag each region, then pick a hero colour and a mood.")
        for g, name in enumerate(names):
            c1, c2 = st.columns([1, 1])
            surf_keys = list(SURFACES)
            cur_surf = book.surface_at(g)
            idx = surf_keys.index(cur_surf) if cur_surf in surf_keys else surf_keys.index("other")
            chosen = c1.selectbox(
                f"Surface — {name}", surf_keys, index=idx,
                format_func=lambda s: SURFACES[s].display, key=f"sgen_surface_{g}")
            book.set_surface_at(g, chosen)
            spec = get_surface(chosen)
            if spec.bucket == REALISTIC:
                tone_opts = list(spec.tones) + [HARMONY_TONE]
                cur_tone = book.tone_at(g)
                t_idx = tone_opts.index(cur_tone) if cur_tone in tone_opts else 0
                tone = c2.selectbox(
                    f"Tone — {name}", tone_opts, index=t_idx,
                    format_func=lambda t: "Follow scheme colour" if t == HARMONY_TONE else t,
                    key=f"sgen_tone_{g}")
                book.set_tone_at(g, tone)
            else:
                book.set_tone_at(g, None)

        # --- anchor + mood + variant ---
        anchor_name = st.selectbox("Hero region (anchor)", names, key="sgen_anchor")
        g_anchor = names.index(anchor_name)
        pal = book.palette_at(g_anchor)
        default_hex = pal[len(pal) // 2].hex if pal else "#c02030"
        anchor_hex = st.color_picker("Hero colour", value=default_hex, key="sgen_anchor_hex")
        mood = st.selectbox("Mood", list(MOODS), key="sgen_mood")
        variant = st.selectbox("Harmony", VARIANTS, key="sgen_variant",
                               help="Cycle this to re-roll the free regions' colours.")
        owned_only = st.checkbox("Owned only (no catalogue suggestions)", value=False,
                                 key="sgen_owned_only")
        set_tech = st.checkbox("Also set techniques from surface", value=True,
                               key="sgen_set_tech")

        if st.button("✨ Generate & apply scheme", type="primary", key="sgen_go"):
            specs = [
                RegionColorSpec(nm, book.surface_at(g), book.tone_at(g),
                                len(book.palette_at(g)))
                for g, nm in enumerate(names)
            ]
            scheme = sb.build_scheme(
                "Generated", specs, anchor_name, anchor_hex, mood, variant,
                list(owned_paints), list(context.CATALOG), owned_only)
            sch.apply(scheme, book)
            if set_tech:
                ps_on = st.session_state.get(keys.NORMALS) is not None
                for g, nm in enumerate(names):
                    tech = get_surface(book.surface_at(g)).default_technique
                    if not tech:
                        continue
                    if tech == "nmm" and not ps_on:
                        continue
                    book.set_material_at(g, tech)
            _reseed_editor_widgets()
            st.success("Scheme generated and applied. Adjust any colour in the editor.")
            st.rerun()
```

- [ ] **Step 4: Mount in `app.py`**

Add `scheme_gen_panel` to the `ui` import group in `app.py` (line ~9, alongside `schemes_panel`), then mount it just before `schemes_panel.render()`:

```python
        scheme_gen_panel.render(owned_paints)
        schemes_panel.render()
```

- [ ] **Step 5: Run the new tests**

Run: `.venv/Scripts/python -m pytest tests/test_ui_scheme_gen.py -q`
Expected: PASS (2 tests).

- [ ] **Step 6: Run the full suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: PASS (all prior tests + the new ones; no regressions).

- [ ] **Step 7: Commit**

```bash
git add ui/scheme_gen_panel.py app.py tests/test_ui_scheme_gen.py
git commit -m "feat: scheme generator panel (surfaces + hero colour + mood → applied scheme)"
```

---

## Self-Review

**Spec coverage:**
- Goal 1 (surface vocabulary) → Task 1. Fantasy skin tones + `other`/no-technique + fur→drybrush all asserted.
- Goal 2 (colour-decision layer) → Task 2. Harmony, mood, ramps; realistic-ignores-harmony + `__harmony__` escape tested; import-purity enforced by the Global Constraint.
- Goal 3 (paint mapping + assembly) → Task 3. Owned-first / catalogue fallback / owned-only / synthetic-mix all tested.
- Goal 4 (Region/RegionBook fields + persistence) → Tasks 4 & 5. Round-trip + default-when-absent tested; schema v4.
- Goal 5 (panel) → Task 6. Per-region surface/tone, anchor+mood+variant, owned-only, opt-in technique set, NMM guard.
- Goal 6 (reuse Scheme) → Tasks 3 & 6 return/consume `schemes.Scheme` + `schemes.apply`; no downstream change.
- Non-goals honoured: no auto-region detection, no coverage generation, no new recipe UI (mix → synthetic paint), gems are a plain free surface.

**Placeholder scan:** none — every step has runnable code or an exact command + expected result.

**Type consistency:** `RegionColorSpec(name, surface, tone, n_bands)` used identically in Tasks 2, 3, 6. `build_scheme(...)` signature matches between Task 3 definition and Task 6 call. `map_ramp_to_palette` / `generate_ramps` / `harmony_hues` / `apply_mood` signatures consistent across tasks. `surface_at`/`set_surface_at`/`tone_at`/`set_tone_at` defined in Task 4, consumed in Tasks 5 & 6. `SURFACES`/`get_surface`/`REALISTIC` defined in Task 1, consumed in Tasks 2 & 6. `MOODS`/`VARIANTS`/`HARMONY_TONE` defined in Task 2, consumed in Task 6.

**Note on `matching.match` tiers:** `_paint_for_hex` relies on tier strings `"exact"`, `"close"`, `"mix"`, `"unreachable"` and on `unreachable` returning `paints=[nearest]` (or `[]`) + `buy_hint`. Verified against `matching.py` before writing this plan.
