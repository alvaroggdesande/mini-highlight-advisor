# Palette Matcher & Mix Advisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Given a target colour (plan band, recipe step, or ad-hoc pick), tell the painter how to reproduce it from the paints they own — exact, close single, mix, or unreachable — with honest consistency guidance.

**Architecture:** Two pure engines (`color.py` for perceptual distance, `matching.py` for the four-tier resolver) feed a pure `consistency.py` annotator; `advisor.py` composes them into renderable rows; `app.py` gets a thin, re-homeable UI section plus an ad-hoc hex input. No new persisted data model — every source normalises to a `Target(hex, preferred_code)`.

**Tech Stack:** Python 3.10+, numpy, Streamlit, pytest. No new dependencies — CIEDE2000 is vendored (offline/free constraint).

## Global Constraints

- **Offline / free.** No network calls, no new paid or online dependencies. Colour conversion is vendored, not a library.
- **Guidance-only mixing.** Never render a mixed colour as an accurate swatch; mixes are labelled approximate.
- **Inventory = owned paints only** for tiers 1–3. Full catalogue is used only for the unreachable buy-hint.
- **Pure engines.** `color.py`, `matching.py`, `consistency.py`, `advisor.py` contain no Streamlit and no file I/O.
- **Follow existing style:** `from __future__ import annotations`, frozen dataclasses, `PaintColor` (`name`, `hex`, `brand`, `paint_range`, `code`, `.rgb`) as the paint type. Tests use bare `pytest` functions importing from `mini_highlight_advisor.*`.
- **Tunables as module constants** in `matching.py`: `EXACT_THRESHOLD = 1.0`, `CLOSE_THRESHOLD = 5.0`, `MIX_ACCEPT_THRESHOLD = 8.0`, `MIX_RATIOS = [(1, 1), (2, 1), (1, 2), (3, 1), (1, 3)]` (all ΔE00).

---

### Task 1: Perceptual colour distance (`color.py`)

Vendored sRGB→CIELab (D65) and CIEDE2000. Everything downstream ranks colours through `delta_e00`.

**Files:**
- Create: `src/mini_highlight_advisor/color.py`
- Test: `tests/test_color.py`

**Interfaces:**
- Consumes: nothing (stdlib `math`, numpy).
- Produces:
  - `hex_to_rgb(hexv: str) -> tuple[float, float, float]` — 0–255 floats.
  - `rgb_to_lab(rgb) -> tuple[float, float, float]` — accepts a 3-seq or numpy array of 0–255 values.
  - `lab_of_hex(hexv: str) -> tuple[float, float, float]`.
  - `delta_e00(lab1, lab2) -> float` — CIEDE2000, kL=kC=kH=1.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_color.py
import math
from mini_highlight_advisor.color import hex_to_rgb, rgb_to_lab, lab_of_hex, delta_e00


def test_hex_to_rgb_parses():
    assert hex_to_rgb("#ffffff") == (255.0, 255.0, 255.0)
    assert hex_to_rgb("000000") == (0.0, 0.0, 0.0)


def test_rgb_to_lab_known_anchors():
    L, a, b = rgb_to_lab((255, 255, 255))
    assert abs(L - 100.0) < 0.5 and abs(a) < 1.0 and abs(b) < 1.0
    L0, _, _ = rgb_to_lab((0, 0, 0))
    assert abs(L0) < 0.5


def test_delta_e00_identity_is_zero():
    lab = lab_of_hex("#6d7173")
    assert delta_e00(lab, lab) == 0.0 or delta_e00(lab, lab) < 1e-9


def test_delta_e00_symmetric():
    a = lab_of_hex("#3f4442")
    b = lab_of_hex("#a7a9a6")
    assert abs(delta_e00(a, b) - delta_e00(b, a)) < 1e-9


def test_delta_e00_orders_by_similarity():
    target = lab_of_hex("#6d7173")      # neutral grey
    near = lab_of_hex("#707173")        # a hair off
    far = lab_of_hex("#1b1b1b")         # near black
    assert delta_e00(target, near) < delta_e00(target, far)


def test_delta_e00_black_white_is_large():
    assert delta_e00(lab_of_hex("#000000"), lab_of_hex("#ffffff")) > 90.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_color.py -v`
Expected: FAIL with `ModuleNotFoundError: mini_highlight_advisor.color`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/mini_highlight_advisor/color.py
from __future__ import annotations

import math


def hex_to_rgb(hexv: str) -> tuple[float, float, float]:
    h = hexv.lstrip("#")
    return tuple(float(int(h[i : i + 2], 16)) for i in (0, 2, 4))  # type: ignore[return-value]


def _srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb_to_lab(rgb) -> tuple[float, float, float]:
    r, g, b = (_srgb_to_linear(float(v)) for v in rgb)
    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505
    xn, yn, zn = 0.95047, 1.0, 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)

    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def lab_of_hex(hexv: str) -> tuple[float, float, float]:
    return rgb_to_lab(hex_to_rgb(hexv))


def delta_e00(lab1, lab2) -> float:
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    avg_Lp = (L1 + L2) / 2.0
    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    avg_C = (C1 + C2) / 2.0
    G = 0.5 * (1 - math.sqrt((avg_C ** 7) / (avg_C ** 7 + 25 ** 7))) if avg_C > 0 else 0.0
    a1p, a2p = a1 * (1 + G), a2 * (1 + G)
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    avg_Cp = (C1p + C2p) / 2.0
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    if abs(h1p - h2p) > 180:
        avg_Hp = (h1p + h2p + 360) / 2.0
    else:
        avg_Hp = (h1p + h2p) / 2.0
    T = (
        1
        - 0.17 * math.cos(math.radians(avg_Hp - 30))
        + 0.24 * math.cos(math.radians(2 * avg_Hp))
        + 0.32 * math.cos(math.radians(3 * avg_Hp + 6))
        - 0.20 * math.cos(math.radians(4 * avg_Hp - 63))
    )
    delta_hp = h2p - h1p
    if abs(delta_hp) > 180:
        delta_hp += 360 if h2p <= h1p else -360
    delta_Lp = L2 - L1
    delta_Cp = C2p - C1p
    delta_Hp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(delta_hp) / 2.0)
    S_L = 1 + (0.015 * (avg_Lp - 50) ** 2) / math.sqrt(20 + (avg_Lp - 50) ** 2)
    S_C = 1 + 0.045 * avg_Cp
    S_H = 1 + 0.015 * avg_Cp * T
    delta_ro = 30 * math.exp(-(((avg_Hp - 275) / 25) ** 2))
    R_C = 2 * math.sqrt((avg_Cp ** 7) / (avg_Cp ** 7 + 25 ** 7)) if avg_Cp > 0 else 0.0
    R_T = -R_C * math.sin(math.radians(2 * delta_ro))
    return math.sqrt(
        (delta_Lp / S_L) ** 2
        + (delta_Cp / S_C) ** 2
        + (delta_Hp / S_H) ** 2
        + R_T * (delta_Cp / S_C) * (delta_Hp / S_H)
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_color.py -v`
Expected: PASS (all 6).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/color.py tests/test_color.py
git commit -m "feat: vendored sRGB->Lab + CIEDE2000 colour distance"
```

---

### Task 2: The matching engine (`matching.py`)

Normalise any source to a `Target`, resolve to one of four tiers against owned paints.

**Files:**
- Create: `src/mini_highlight_advisor/matching.py`
- Test: `tests/test_matching.py`

**Interfaces:**
- Consumes: `color.lab_of_hex`, `color.delta_e00`, `color.hex_to_rgb`; `palette.PaintColor`.
- Produces:
  - `Target(hex: str, preferred_code: str | None = None)` (frozen dataclass).
  - `target_from_band(hexv: str) -> Target`.
  - `target_from_recipe_step(step) -> Target` — reads `step.hex`, `step.paint_ref`.
  - `target_from_hex(hexv: str) -> Target`.
  - `MatchResult(tier, target_hex, paints, parts, delta_e, buy_hint, phrase)` (frozen dataclass; `tier` in `"exact"|"close"|"mix"|"unreachable"`).
  - `match(target: Target, owned: list[PaintColor], catalog: list[PaintColor]) -> MatchResult`.
  - Constants: `EXACT_THRESHOLD`, `CLOSE_THRESHOLD`, `MIX_ACCEPT_THRESHOLD`, `MIX_RATIOS`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_matching.py
from mini_highlight_advisor.palette import PaintColor
from mini_highlight_advisor.matching import (
    Target, target_from_band, target_from_recipe_step, target_from_hex,
    match, MatchResult,
)
from mini_highlight_advisor.recipes import RecipeStep

BLACK = PaintColor("Black", "#1b1b1b", code="70.950")
GREY = PaintColor("Neutral Grey", "#6d7173", code="70.991")
WHITE = PaintColor("Dead White", "#f3f3ee", code="70.951")
CATALOG = [BLACK, GREY, WHITE, PaintColor("Sky Blue", "#4a90d9", code="72.022")]


def test_normalizers():
    assert target_from_band("#123456") == Target("#123456", None)
    assert target_from_hex("#abcdef") == Target("#abcdef", None)
    step = RecipeStep(label="Base", hex="#6d7173", paint_ref="70.991")
    assert target_from_recipe_step(step) == Target("#6d7173", "70.991")


def test_exact_by_preferred_code():
    res = match(Target("#6d7173", "70.991"), owned=[GREY, WHITE], catalog=CATALOG)
    assert res.tier == "exact"
    assert res.paints == [GREY]


def test_exact_by_near_zero_distance():
    res = match(Target("#6e7274", None), owned=[GREY, WHITE], catalog=CATALOG)
    assert res.tier == "exact"
    assert res.paints == [GREY]


def test_close_single_within_threshold():
    # a grey clearly off from #6d7173 but still within CLOSE_THRESHOLD
    res = match(Target("#787b7d", None), owned=[GREY, WHITE], catalog=CATALOG)
    assert res.tier == "close"
    assert res.paints == [GREY]
    assert res.delta_e > 1.0


def test_mix_when_between_two_owned():
    # midway grey reachable only by mixing black + white; no single owned grey
    res = match(Target("#8a8a88", None), owned=[BLACK, WHITE], catalog=CATALOG)
    assert res.tier == "mix"
    assert len(res.paints) == 2
    assert res.parts is not None and len(res.parts) == 2
    assert "approx" in res.phrase.lower()


def test_unreachable_gives_buy_hint():
    # vivid blue target, owner has only greys -> unreachable + buy hint from catalog
    res = match(Target("#4a90d9", None), owned=[BLACK, GREY, WHITE], catalog=CATALOG)
    assert res.tier == "unreachable"
    assert res.buy_hint is not None
    assert res.buy_hint.code == "72.022"          # the Sky Blue they don't own
    assert res.buy_hint not in [BLACK, GREY, WHITE]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_matching.py -v`
Expected: FAIL with `ModuleNotFoundError: mini_highlight_advisor.matching`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/mini_highlight_advisor/matching.py
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .color import delta_e00, hex_to_rgb, lab_of_hex, rgb_to_lab
from .palette import PaintColor

EXACT_THRESHOLD = 1.0
CLOSE_THRESHOLD = 5.0
MIX_ACCEPT_THRESHOLD = 8.0
MIX_RATIOS = [(1, 1), (2, 1), (1, 2), (3, 1), (1, 3)]


@dataclass(frozen=True)
class Target:
    hex: str
    preferred_code: str | None = None


def target_from_band(hexv: str) -> Target:
    return Target(hexv, None)


def target_from_hex(hexv: str) -> Target:
    return Target(hexv, None)


def target_from_recipe_step(step) -> Target:
    return Target(step.hex, step.paint_ref)


@dataclass(frozen=True)
class MatchResult:
    tier: str
    target_hex: str
    paints: list[PaintColor]
    parts: list[int] | None
    delta_e: float
    buy_hint: PaintColor | None
    phrase: str


def _deviation(t_lab, p_lab) -> str:
    parts: list[str] = []
    if abs(p_lab[0] - t_lab[0]) > 2:
        parts.append("lighter" if p_lab[0] > t_lab[0] else "darker")
    if abs(p_lab[2] - t_lab[2]) > 2:
        parts.append("warmer" if p_lab[2] > t_lab[2] else "cooler")
    return " & ".join(parts) if parts else "very close"


def _best_mix(t_lab, owned: list[PaintColor]):
    """Return (paintA, paintB, [a, b], delta_e) of the closest 2-paint blend, or None."""
    best = None
    for i in range(len(owned)):
        for j in range(i + 1, len(owned)):
            a_rgb = owned[i].rgb
            b_rgb = owned[j].rgb
            for wa, wb in MIX_RATIOS:
                blended = (wa * a_rgb + wb * b_rgb) / (wa + wb)   # approximate, sRGB space
                d = delta_e00(t_lab, rgb_to_lab(blended))
                if best is None or d < best[3]:
                    best = (owned[i], owned[j], [wa, wb], d)
    return best


def match(target: Target, owned: list[PaintColor], catalog: list[PaintColor]) -> MatchResult:
    t_lab = lab_of_hex(target.hex)

    # Tier 1a: exact by owned preferred code
    if target.preferred_code:
        for p in owned:
            if p.code and p.code == target.preferred_code:
                d = delta_e00(t_lab, lab_of_hex(p.hex))
                return MatchResult("exact", target.hex, [p], None, d, None,
                                   f"Use {p.name} ({p.code}).")

    # rank owned by perceptual distance
    ranked = sorted(owned, key=lambda p: delta_e00(t_lab, lab_of_hex(p.hex)))
    if ranked:
        nearest = ranked[0]
        d0 = delta_e00(t_lab, lab_of_hex(nearest.hex))
        # Tier 1b: exact by near-zero distance
        if d0 <= EXACT_THRESHOLD:
            return MatchResult("exact", target.hex, [nearest], None, d0, None,
                               f"Use {nearest.name} ({nearest.code}).".replace(" ().", "."))
        # Tier 2: close single
        if d0 <= CLOSE_THRESHOLD:
            dev = _deviation(t_lab, lab_of_hex(nearest.hex))
            return MatchResult("close", target.hex, [nearest], None, d0, None,
                               f"Closest you own: {nearest.name} — {dev} (ΔE {d0:.1f}).")

    # Tier 3: mix
    mix = _best_mix(t_lab, owned) if len(owned) >= 2 else None
    if mix and mix[3] <= MIX_ACCEPT_THRESHOLD:
        a, b, parts, d = mix
        return MatchResult("mix", target.hex, [a, b], parts, d, None,
                           f"Mix ~{parts[0]}:{parts[1]} {a.name} + {b.name} (approx).")

    # Tier 4: unreachable + buy hint from full catalogue
    owned_codes = {p.code for p in owned if p.code}
    unowned = [p for p in catalog if p.code not in owned_codes]
    buy = min(unowned, key=lambda p: delta_e00(t_lab, lab_of_hex(p.hex))) if unowned else None
    nearest = ranked[0] if ranked else None
    d_near = delta_e00(t_lab, lab_of_hex(nearest.hex)) if nearest else float("nan")
    phrase = "Can't match with what you own"
    if nearest:
        phrase += f" (nearest {nearest.name}, ΔE {d_near:.1f})"
    if buy:
        phrase += f". Or buy {buy.name}."
    return MatchResult("unreachable", target.hex, [nearest] if nearest else [], None,
                       d_near, buy, phrase)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_matching.py -v`
Expected: PASS (all 6). If `test_close_single_within_threshold` or `test_mix_when_between_two_owned` land on the wrong side of a threshold, adjust the **test hex** (not the constant) so the intended tier is exercised — the constants are the spec's defaults.

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/matching.py tests/test_matching.py
git commit -m "feat: four-tier palette matching engine (exact/close/mix/unreachable)"
```

---

### Task 3: Consistency notes (`consistency.py`)

Annotate a `MatchResult` with one working-consistency line: per-role dilution + mix water ratio + paint-type caveats.

**Files:**
- Create: `src/mini_highlight_advisor/consistency.py`
- Test: `tests/test_consistency.py`

**Interfaces:**
- Consumes: `matching.MatchResult`; `palette.PaintColor`.
- Produces:
  - `annotate(result: MatchResult, role: str) -> str` — one line; `""` if nothing applies.
  - Module constants `ROLE_DILUTION: dict[str, str]`, and internal keyword rules for paint-type caveats.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_consistency.py
from mini_highlight_advisor.palette import PaintColor
from mini_highlight_advisor.matching import MatchResult
from mini_highlight_advisor.consistency import annotate


def _res(tier="close", paints=None):
    paints = paints or [PaintColor("Neutral Grey", "#6d7173")]
    return MatchResult(tier, "#6d7173", paints, None, 2.0, None, "x")


def test_role_dilution_base():
    note = annotate(_res(), role="Base")
    assert "thin coats" in note


def test_edge_highlight_role():
    note = annotate(_res(), role="Edge Highlight")
    assert "fine" in note.lower() or "tip" in note.lower()


def test_mix_adds_water_ratio():
    res = MatchResult("mix", "#8a8a88", [PaintColor("Black", "#1b1b1b"),
                      PaintColor("White", "#f3f3ee")], [1, 1], 3.0, None, "x")
    note = annotate(res, role="Midtone")
    assert "milk" in note.lower() or "consistency" in note.lower()


def test_metallic_caveat():
    res = _res(paints=[PaintColor("Gunmetal", "#5a5f63", paint_range="Metal Color")])
    note = annotate(res, role="Base")
    assert "stir" in note.lower() or "settle" in note.lower()


def test_low_opacity_caveat():
    res = _res(paints=[PaintColor("Dead White", "#f3f3ee")])
    note = annotate(res, role="Highlight")
    assert "coat" in note.lower()


def test_unknown_role_no_dilution_but_still_string():
    note = annotate(_res(), role="")
    assert isinstance(note, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_consistency.py -v`
Expected: FAIL with `ModuleNotFoundError: mini_highlight_advisor.consistency`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/mini_highlight_advisor/consistency.py
from __future__ import annotations

from .matching import MatchResult
from .palette import PaintColor

ROLE_DILUTION = {
    "Shadow": "2 thin coats, milk-like.",
    "Base": "2 thin coats, milk-like.",
    "Midtone": "thinned more, build up gradually.",
    "Highlight": "thinned more, build up gradually.",
    "Edge Highlight": "thinned, fine controlled tip.",
}

_METALLIC = ("metal", "steel", "gold", "silver", "bronze", "chrome", "gunmetal", "iron")
_LOW_OPACITY = ("white", "yellow")
_FLOW = ("ink", "wash", "contrast")


def _paint_type_caveat(paints: list[PaintColor]) -> str:
    blob = " ".join(f"{p.name} {p.paint_range or ''}" for p in paints).lower()
    if any(k in blob for k in _METALLIC):
        return "Metallic: stir often, settles."
    if any(k in blob for k in _LOW_OPACITY):
        return "Low opacity: expect extra coats."
    if any(k in blob for k in _FLOW):
        return "Flows: one pass."
    return ""


def annotate(result: MatchResult, role: str) -> str:
    parts: list[str] = []
    if role in ROLE_DILUTION:
        parts.append(ROLE_DILUTION[role])
    if result.tier == "mix":
        parts.append("Thin the mix to milk consistency.")
    caveat = _paint_type_caveat(result.paints)
    if caveat:
        parts.append(caveat)
    return " ".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_consistency.py -v`
Expected: PASS (all 6).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/consistency.py tests/test_consistency.py
git commit -m "feat: consistency notes (role dilution + mix water + paint-type caveats)"
```

---

### Task 4: Advisor composition (`advisor.py`)

Compose matching + consistency into renderable rows. This is the unit-testable seam the UI renders; it keeps all logic out of `app.py`.

**Files:**
- Create: `src/mini_highlight_advisor/advisor.py`
- Test: `tests/test_advisor.py`

**Interfaces:**
- Consumes: `matching.Target`, `matching.match`, `matching.MatchResult`; `consistency.annotate`; `palette.PaintColor`.
- Produces:
  - `AdviceRow(role: str, result: MatchResult, note: str)` (frozen dataclass).
  - `advise(targets: list[Target], roles: list[str], owned: list[PaintColor], catalog: list[PaintColor]) -> list[AdviceRow]` — zips targets with roles (role `""` when a source has none).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_advisor.py
from mini_highlight_advisor.palette import PaintColor
from mini_highlight_advisor.matching import Target
from mini_highlight_advisor.advisor import advise, AdviceRow

BLACK = PaintColor("Black", "#1b1b1b", code="70.950")
GREY = PaintColor("Neutral Grey", "#6d7173", code="70.991")
WHITE = PaintColor("Dead White", "#f3f3ee", code="70.951")
CATALOG = [BLACK, GREY, WHITE]


def test_advise_zips_targets_and_roles():
    targets = [Target("#6d7173", "70.991"), Target("#f3f3ee", None)]
    rows = advise(targets, ["Base", "Edge Highlight"], owned=[GREY, WHITE], catalog=CATALOG)
    assert len(rows) == 2
    assert all(isinstance(r, AdviceRow) for r in rows)
    assert rows[0].role == "Base"
    assert rows[0].result.tier == "exact"
    assert "thin coats" in rows[0].note          # consistency was applied


def test_advise_tolerates_missing_roles():
    rows = advise([Target("#6d7173", None)], roles=[], owned=[GREY], catalog=CATALOG)
    assert len(rows) == 1
    assert rows[0].role == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_advisor.py -v`
Expected: FAIL with `ModuleNotFoundError: mini_highlight_advisor.advisor`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/mini_highlight_advisor/advisor.py
from __future__ import annotations

from dataclasses import dataclass
from itertools import zip_longest

from .consistency import annotate
from .matching import MatchResult, Target, match
from .palette import PaintColor


@dataclass(frozen=True)
class AdviceRow:
    role: str
    result: MatchResult
    note: str


def advise(targets: list[Target], roles: list[str], owned: list[PaintColor],
           catalog: list[PaintColor]) -> list[AdviceRow]:
    rows: list[AdviceRow] = []
    for target, role in zip_longest(targets, roles, fillvalue=""):
        if target == "":            # more roles than targets -> ignore extra roles
            continue
        role = role or ""
        result = match(target, owned, catalog)
        rows.append(AdviceRow(role, result, annotate(result, role)))
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_advisor.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/advisor.py tests/test_advisor.py
git commit -m "feat: advisor composes matching + consistency into advice rows"
```

---

### Task 5: Minimal UI wiring (`app.py`)

Render advice rows and add an ad-hoc hex input. Deliberately thin and self-contained so the future "Prep vs Paint" split can re-home it without touching the engines. No automated UI test — verified by running the app (defer the smoke run to the user).

**Files:**
- Modify: `app.py` (Paints tab — after the palette-builder block, ~line 122; imports near top ~line 7–12)

**Interfaces:**
- Consumes: `advisor.advise`, `matching.target_from_band`, `matching.target_from_hex`, `matching.target_from_recipe_step`; `catalog.find_by_code`, `collection.load`; `palette.role_names`; existing `_swatch` helper and `CATALOG`.
- Produces: no new exported symbols (UI only).

- [ ] **Step 1: Add imports**

At the top of `app.py`, alongside the existing `mini_highlight_advisor` imports:

```python
from mini_highlight_advisor.advisor import advise
from mini_highlight_advisor.matching import (
    target_from_band, target_from_hex, target_from_recipe_step,
)
from mini_highlight_advisor.palette import role_names
```

- [ ] **Step 2: Add the "Match to my paints" section**

In the Paints tab, after the palette-builder / save-as-recipe block, add:

```python
st.divider()
st.markdown("### Match to my paints")
st.caption("How to hit each colour with what you own — checked once while you prep.")

owned_codes = collection.load(catalog=CATALOG)
owned_paints = [p for p in CATALOG if p.code in owned_codes]

# targets: the palette the user just built (dark -> light), with role labels
targets = [target_from_band(p.hex) for p in palette]
roles = role_names(len(palette))

# ad-hoc single colour ("how do I make this?")
adhoc = st.color_picker("Ad-hoc colour", value="#808080", key="adhoc_hex")
if st.checkbox("Include ad-hoc colour", key="adhoc_on"):
    targets = targets + [target_from_hex(adhoc)]
    roles = roles + ["Ad-hoc"]

if not owned_paints:
    st.info("Tick the paints you own (above) to get match suggestions.")
else:
    for row in advise(targets, roles, owned_paints, CATALOG):
        r = row.result
        chips = "".join(_swatch(p.hex) for p in r.paints)
        st.markdown(f"{chips} **{row.role}** — {r.phrase}", unsafe_allow_html=True)
        if row.note:
            st.caption(row.note)
```

- [ ] **Step 3: Verify the app imports and starts**

Run: `.venv/Scripts/python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read()); print('ok')"`
Expected: `ok` (syntax valid).

Then hand off to the user for the live smoke test (per project convention, do not self-run Streamlit):
> "Run `streamlit run app.py`, open the Paints tab, tick a few owned paints, and confirm the 'Match to my paints' section shows exact/close/mix/unreachable lines + consistency notes, and that the ad-hoc colour toggle adds a row."

- [ ] **Step 4: Run the full test suite (nothing regressed)**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all tests pass (existing + new `test_color`, `test_matching`, `test_consistency`, `test_advisor`).

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: 'match to my paints' UI section + ad-hoc colour input"
```

---

## Self-Review

**Spec coverage:**
- Target normalisation (plan/recipe/ad-hoc) → Task 2 (`target_from_*`), wired in Task 5. ✅
- Owned-only inventory → Tasks 2 & 5 (`owned_paints`). ✅
- CIEDE2000 in Lab + `CLOSE_THRESHOLD` → Task 1 + Task 2 constants. ✅
- Four tiers (exact / close / mix / unreachable + buy-hint) → Task 2, all six tests. ✅
- Guidance-only mix, no accurate swatch, "approx" label → Task 2 phrase + no swatch rendered for the *estimated* mix (only the two real paint chips shown in Task 5). ✅
- Consistency: role dilution + mix water + paint-type caveats → Task 3. ✅
- Minimal, re-homeable UI + future Prep/Paint split noted as out of scope → Task 5. ✅
- Offline/free, no new deps → vendored `color.py`, Global Constraints. ✅

**Placeholder scan:** No TBD/TODO; every code and test step is concrete. ✅

**Type consistency:** `PaintColor` (`.rgb`, `.code`, `.paint_range`) used consistently; `MatchResult` field names identical across Tasks 2–5; `Target`/`AdviceRow` signatures match their consumers; `advise(targets, roles, owned, catalog)` order consistent between Task 4 def and Task 5 call. ✅

**Note for implementer:** Tasks 1→4 are strictly sequential (each imports the previous). Task 5 depends on all. Threshold-boundary tests (Task 2) may need the *test hex* nudged, never the constants.
