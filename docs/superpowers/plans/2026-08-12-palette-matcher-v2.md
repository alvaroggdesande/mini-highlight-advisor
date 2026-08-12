# Palette-Matcher v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach the palette matcher about paint *finish* (matte/metallic/wash/contrast) so it never blends across finishes, and extend mixing from 2 to (capped, ΔE-gated) 3 paints with a physically honest linear-light blend.

**Architecture:** A new `finish` property on `PaintColor` (default `matte`, read from the catalogue) flows into `Target` via `target_from_paint`. `matching.py` filters every candidate pool by finish, runs a bounded 2–3 paint mix search (top-K nearest legal singles, coprime ratios summing ≤ 4), blends in linear-light (`color.linear_blend`), and gates 3-paint mixes behind a ΔE improvement margin. `consistency.py` switches to the flag with a keyword fallback. The catalogue gets a curation pass tagging real metallics.

**Tech Stack:** Python 3.11, numpy, Streamlit, pytest. No new dependencies (offline/free constraint holds).

## Global Constraints

- **Offline / free.** No network calls, no new dependencies. Colour maths stay vendored in `color.py`.
- **Guidance-only mixing.** Never render a mixed colour as an accurate swatch; every mix phrase ends with `(approx)`.
- **Pure engines.** `color.py`, `matching.py`, `consistency.py`, `advisor.py` contain no Streamlit and no file I/O.
- **Follow existing style:** `from __future__ import annotations`, frozen dataclasses, `PaintColor(name, hex, brand, paint_range, code, .rgb)` as the paint type. Tests are bare `pytest` functions importing from `mini_highlight_advisor.*`.
- **Run tests with** `.venv/Scripts/python -m pytest`. Do **not** self-run Streamlit — hand the live smoke to the user.
- **Finish taxonomy (exact strings):** `matte | metallic | wash | contrast`. Default is `matte`.
- **Tunables as module constants** in `matching.py`: `EXACT_THRESHOLD = 1.0`, `CLOSE_THRESHOLD = 5.0`, `MIX_ACCEPT_THRESHOLD = 8.0`, `MIX_MAX_PARTS = 4`, `MIX_TOPK = 8`, `MIX_TINT_TOPT = 4`, `TRIPLE_IMPROVE_MARGIN = 1.0`, `_METAL_TINT_RATIOS = [(2, 1), (3, 1)]`.
- **Finish rules (the contract every task upholds):**
  - Single/close/nearest match + buy-hint: **same-finish only**.
  - Matte target mix: **matte ingredients only** (metallic forbidden; wash/contrast excluded).
  - Metallic target mix: **metallic-majority** — 2–3 metallics, *or* one metallic + one non-metallic tint where the tint part is strictly the minority.
  - Wash/contrast targets: **never mixed** (single-match only).

---

### Task 1: `finish` on the paint model + catalogue loader

Add the `finish` field to `PaintColor` and teach `catalog.py` to read and validate it. Default-on-load keeps every existing matte entry untouched.

**Files:**
- Modify: `src/mini_highlight_advisor/palette.py:8-19` (the `PaintColor` dataclass)
- Modify: `src/mini_highlight_advisor/catalog.py:11-52` (validation + load)
- Test: `tests/test_palette.py` (add), `tests/test_catalog.py` (add)

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `PaintColor(name, hex, brand=None, paint_range=None, code="", finish="matte")` — new trailing field `finish: str`.
  - `catalog.validate_catalog` rejects any `finish` outside `{matte, metallic, wash, contrast}`.
  - `catalog.load_catalog` sets `finish=p.get("finish", "matte")`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_palette.py`:

```python
def test_paintcolor_finish_defaults_matte():
    from mini_highlight_advisor.palette import PaintColor
    assert PaintColor("X", "#111111").finish == "matte"


def test_paintcolor_finish_explicit():
    from mini_highlight_advisor.palette import PaintColor
    assert PaintColor("Silver", "#c9cccd", finish="metallic").finish == "metallic"
```

Append to `tests/test_catalog.py`:

```python
def test_load_defaults_finish_matte(tmp_path):
    import json
    from mini_highlight_advisor.catalog import load_catalog
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"paints": [{"code": "70.950", "name": "Black", "hex": "#1b1b1b"}]}))
    assert load_catalog(p)[0].finish == "matte"


def test_load_reads_metallic_finish(tmp_path):
    import json
    from mini_highlight_advisor.catalog import load_catalog
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"paints": [
        {"code": "77.101", "name": "Sterling Silver", "hex": "#d5d7d6", "finish": "metallic"}]}))
    assert load_catalog(p)[0].finish == "metallic"


def test_validate_rejects_bad_finish():
    from mini_highlight_advisor.catalog import validate_catalog
    with pytest.raises(ValueError) as exc:
        validate_catalog([{"code": "1", "name": "Glitterbomb", "hex": "#111111", "finish": "glitter"}])
    assert "finish" in str(exc.value) and "Glitterbomb" in str(exc.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_palette.py tests/test_catalog.py -q`
Expected: FAIL — `PaintColor` has no `finish`; `validate_catalog` accepts the bad finish.

- [ ] **Step 3: Add the `finish` field to `PaintColor`**

In `src/mini_highlight_advisor/palette.py`, extend the dataclass:

```python
@dataclass(frozen=True)
class PaintColor:
    name: str
    hex: str
    brand: str | None = None
    paint_range: str | None = None
    code: str = ""
    finish: str = "matte"

    @property
    def rgb(self) -> np.ndarray:
        h = self.hex.lstrip("#")
        return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)
```

- [ ] **Step 4: Validate + load `finish` in `catalog.py`**

In `src/mini_highlight_advisor/catalog.py`, add the allowed-set constant near the top (after `_HEX_RE`):

```python
_FINISHES = {"matte", "metallic", "wash", "contrast"}
```

In `validate_catalog`, after the hex check and before the duplicate-code check, add:

```python
        fin = p.get("finish")
        if fin is not None and fin not in _FINISHES:
            raise ValueError(
                f"Catalogue paint {name!r} ({code}) has invalid finish {fin!r}; "
                f"expected one of {sorted(_FINISHES)}."
            )
```

In `load_catalog`, add `finish` to the `PaintColor(...)` construction:

```python
        PaintColor(
            name=p["name"],
            hex=p["hex"],
            brand=p.get("brand"),
            paint_range=p.get("range"),
            code=p.get("code", ""),
            finish=p.get("finish", "matte"),
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_palette.py tests/test_catalog.py -q`
Expected: PASS (new tests green; existing catalogue/palette tests still green — `finish` is a trailing default).

- [ ] **Step 6: Commit**

```bash
git add src/mini_highlight_advisor/palette.py src/mini_highlight_advisor/catalog.py tests/test_palette.py tests/test_catalog.py
git commit -m "feat: paint finish field (matte/metallic/wash/contrast) on model + catalogue loader"
```

---

### Task 2: Linear-light blend helper (`color.py`)

Replace the naive sRGB average with an honest linear-light blend. Pure function, numpy-free (keeps `color.py` dependency-light); returns a 0–255 sRGB tuple that `rgb_to_lab` already accepts.

**Files:**
- Modify: `src/mini_highlight_advisor/color.py` (append helpers)
- Test: `tests/test_color.py` (add)

**Interfaces:**
- Consumes: existing `_srgb_to_linear` (0–255 in → 0–1 linear out).
- Produces:
  - `linear_blend(rgbs, parts) -> tuple[float, float, float]` — `rgbs` is a sequence of 3-seqs (0–255, e.g. `PaintColor.rgb`), `parts` a sequence of positive ints; averages in linear-light weighted by parts, returns 0–255 sRGB.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_color.py`:

```python
def test_linear_blend_midpoint_lighter_than_srgb_average():
    from mini_highlight_advisor.color import linear_blend
    r, g, b = linear_blend([(0, 0, 0), (255, 255, 255)], [1, 1])
    assert 180 < r < 195          # linear-light mid ≈ 188, not the 127 of an sRGB average
    assert abs(r - g) < 1e-6 and abs(g - b) < 1e-6


def test_linear_blend_respects_parts():
    from mini_highlight_advisor.color import linear_blend
    dark = linear_blend([(0, 0, 0), (255, 255, 255)], [3, 1])
    light = linear_blend([(0, 0, 0), (255, 255, 255)], [1, 3])
    assert dark[0] < light[0]


def test_linear_blend_single_is_identity():
    from mini_highlight_advisor.color import linear_blend
    r, g, b = linear_blend([(120, 60, 30)], [1])
    assert abs(r - 120) < 1.0 and abs(g - 60) < 1.0 and abs(b - 30) < 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_color.py -q`
Expected: FAIL with `ImportError: cannot import name 'linear_blend'`.

- [ ] **Step 3: Add the helpers**

Append to `src/mini_highlight_advisor/color.py`:

```python
def _linear_to_srgb255(v: float) -> float:
    v = max(0.0, min(1.0, v))
    s = 12.92 * v if v <= 0.0031308 else 1.055 * (v ** (1 / 2.4)) - 0.055
    return s * 255.0


def linear_blend(rgbs, parts) -> tuple[float, float, float]:
    """Blend sRGB colours (0-255 seqs) by integer `parts` in linear-light space.

    Physically more honest than averaging sRGB directly. Still an approximation of
    real pigment mixing — callers label the result 'approx'.
    """
    total = float(sum(parts))
    acc = [0.0, 0.0, 0.0]
    for rgb, w in zip(rgbs, parts):
        for k in range(3):
            acc[k] += w * _srgb_to_linear(float(rgb[k]))
    return tuple(_linear_to_srgb255(acc[k] / total) for k in range(3))  # type: ignore[return-value]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_color.py -q`
Expected: PASS (existing 6 + new 3).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/color.py tests/test_color.py
git commit -m "feat: linear-light blend helper for honest paint-mix estimates"
```

---

### Task 3: Finish-aware matcher + 2→3 paint mix engine (`matching.py`)

Rewrite `matching.py`: `Target.finish`, same-finish single/buy pools, a bounded 2–3 paint mix search with the metallic-tint rule, linear-light ΔE, and the 3-paint complexity gate. This is a full-file replace — the file stays small.

**Files:**
- Modify: `src/mini_highlight_advisor/matching.py` (full replace)
- Test: `tests/test_matching.py` (add cases; existing cases must still pass)

**Interfaces:**
- Consumes: `color.delta_e00`, `color.lab_of_hex`, `color.rgb_to_lab`, `color.linear_blend`; `palette.PaintColor`.
- Produces:
  - `Target(hex: str, preferred_code: str | None = None, finish: str = "matte")`.
  - `target_from_band`, `target_from_hex`, `target_from_recipe_step` (finish defaults `matte`); `target_from_paint(paint)` inherits `paint.finish`.
  - `MatchResult(tier, target_hex, paints, parts, delta_e, buy_hint, phrase)` — unchanged shape; `paints`/`parts` now hold up to 3 entries.
  - `match(target, owned, catalog) -> MatchResult`.
  - All constants listed in Global Constraints.

- [ ] **Step 1: Add the new failing tests**

Append to `tests/test_matching.py` (keep the existing tests as-is):

```python
SILVER = PaintColor("Sterling Silver", "#d5d7d6", finish="metallic")
DARKMETAL = PaintColor("Obsidian Black", "#292b2c", finish="metallic")


def test_target_from_paint_inherits_finish():
    from mini_highlight_advisor.matching import target_from_paint
    assert target_from_paint(SILVER).finish == "metallic"
    assert target_from_paint(GREY).finish == "matte"


def test_matte_target_never_returns_metallic():
    # SILVER (metallic) must be excluded from a MATTE target's pools
    t = Target("#d3d5d4", None, "matte")   # sits right on the silver hex, but matte
    res = match(t, owned=[SILVER, WHITE], catalog=[SILVER, WHITE])
    assert all(p.finish != "metallic" for p in res.paints)
    if res.buy_hint is not None:
        assert res.buy_hint.finish != "metallic"


def test_metallic_target_matches_metallic_only():
    t = Target("#d5d7d6", None, "metallic")
    res = match(t, owned=[SILVER, GREY, WHITE], catalog=[SILVER])
    assert res.tier == "exact" and res.paints == [SILVER]


def test_metallic_shadow_is_all_metallic_mix():
    t = Target("#7f8182", None, "metallic")     # between silver and dark metal
    res = match(t, owned=[SILVER, DARKMETAL], catalog=[SILVER, DARKMETAL])
    assert res.tier == "mix"
    assert all(p.finish == "metallic" for p in res.paints)


def test_metallic_plus_minority_tint():
    blue = PaintColor("Blue", "#2b5fa8")         # matte tint
    t = Target("#93a1b4", None, "metallic")      # silver pushed toward blue
    res = match(t, owned=[SILVER, blue], catalog=[SILVER, blue])
    # only legal mix is metallic + tint; tint must be the minority part
    assert res.tier == "mix"
    assert res.paints[0].finish == "metallic" and res.paints[1].finish != "metallic"
    assert res.parts[-1] == min(res.parts)
    assert "tint" in res.phrase.lower()


def test_three_paint_mix_when_pair_cannot_reach():
    R = PaintColor("R", "#ff0000"); G = PaintColor("G", "#00ff00"); B = PaintColor("B", "#0000ff")
    t = Target("#9a9a9a", None, "matte")          # neutral grey needs all three
    res = match(t, owned=[R, G, B], catalog=[R, G, B])
    assert res.tier == "mix" and len(res.paints) == 3


def test_two_paint_kept_when_third_barely_helps():
    NEARW = PaintColor("Near White", "#eeeeee")
    t = Target("#8a8a88", None, "matte")          # black+white already nails it
    res = match(t, owned=[BLACK, WHITE, NEARW], catalog=[BLACK, WHITE, NEARW])
    assert res.tier == "mix" and len(res.paints) == 2
```

> **Boundary note:** `test_metallic_plus_minority_tint`, `test_three_paint_mix_when_pair_cannot_reach`, and `test_two_paint_kept_when_third_barely_helps` depend on ΔE landing on the intended side of a threshold. If one lands wrong, nudge the **target hex** in the test (not the module constants) until the intended tier/arity is exercised — the constants are the spec defaults.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_matching.py -q`
Expected: FAIL — `Target` has no `finish`; metallic/3-paint behaviour absent.

- [ ] **Step 3: Replace `matching.py`**

Replace the whole file `src/mini_highlight_advisor/matching.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from itertools import combinations
from math import gcd

from .color import delta_e00, lab_of_hex, linear_blend, rgb_to_lab
from .palette import PaintColor

EXACT_THRESHOLD = 1.0
CLOSE_THRESHOLD = 5.0
MIX_ACCEPT_THRESHOLD = 8.0
MIX_MAX_PARTS = 4            # integer parts of a mix sum to at most this (reproducible at the bench)
MIX_TOPK = 8                # nearest same-finish singles considered as mix ingredients
MIX_TINT_TOPT = 4           # nearest non-metallic singles considered as a metallic tint
TRIPLE_IMPROVE_MARGIN = 1.0  # a 3-paint mix must beat the best 2-paint mix by >= this ΔE
_METAL_TINT_RATIOS = [(2, 1), (3, 1)]   # metal:tint — metal strictly dominant


@dataclass(frozen=True)
class Target:
    hex: str
    preferred_code: str | None = None
    finish: str = "matte"


def target_from_band(hexv: str) -> Target:
    return Target(hexv, None)


def target_from_hex(hexv: str) -> Target:
    return Target(hexv, None)


def target_from_recipe_step(step) -> Target:
    return Target(step.hex, step.paint_ref)


def target_from_paint(paint: PaintColor) -> Target:
    return Target(paint.hex, paint.code or None, paint.finish)


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


def _nearest_first(t_lab, paints: list[PaintColor]) -> list[PaintColor]:
    return sorted(paints, key=lambda p: delta_e00(t_lab, lab_of_hex(p.hex)))


def _ratios(n: int) -> list[tuple[int, ...]]:
    """Coprime integer part-tuples of length n, each part >= 1, summing to <= MIX_MAX_PARTS."""
    out: list[tuple[int, ...]] = []

    def rec(prefix: tuple[int, ...], slots: int, used: int) -> None:
        if slots == 0:
            if reduce(gcd, prefix) == 1:
                out.append(prefix)
            return
        hi = MIX_MAX_PARTS - used - (slots - 1)
        for v in range(1, hi + 1):
            rec(prefix + (v,), slots - 1, used + v)

    rec((), n, 0)
    return out


def _mix_delta(t_lab, paints: list[PaintColor], parts) -> float:
    blended = linear_blend([p.rgb for p in paints], parts)
    return delta_e00(t_lab, rgb_to_lab(blended))


def _candidate_mixes(t_lab, owned: list[PaintColor], finish: str):
    """All finish-legal mix recipes as (paints, parts, delta_e). Empty for wash/contrast."""
    results: list[tuple[list[PaintColor], list[int], float]] = []
    if finish not in ("matte", "metallic"):
        return results
    base = _nearest_first(t_lab, [p for p in owned if p.finish == finish])[:MIX_TOPK]
    for n in (2, 3):
        if len(base) >= n:
            for combo in combinations(base, n):
                for parts in _ratios(n):
                    results.append((list(combo), list(parts), _mix_delta(t_lab, combo, parts)))
    if finish == "metallic":
        tints = _nearest_first(t_lab, [p for p in owned if p.finish != "metallic"])[:MIX_TINT_TOPT]
        for m in base:
            for tnt in tints:
                for wm, wt in _METAL_TINT_RATIOS:
                    results.append(([m, tnt], [wm, wt], _mix_delta(t_lab, [m, tnt], [wm, wt])))
    return results


def _mix_phrase(paints: list[PaintColor], parts: list[int], finish: str) -> str:
    ratio = ":".join(str(p) for p in parts)
    if finish == "metallic" and len(paints) == 2 and paints[1].finish != "metallic":
        return f"Mix {ratio} {paints[0].name} + a touch of {paints[1].name} (tint, approx)."
    names = " + ".join(p.name for p in paints)
    return f"Mix {ratio} {names} (approx)."


def match(target: Target, owned: list[PaintColor], catalog: list[PaintColor]) -> MatchResult:
    t_lab = lab_of_hex(target.hex)

    # Tier 1a: exact by owned preferred code
    if target.preferred_code:
        for p in owned:
            if p.code and p.code == target.preferred_code:
                d = delta_e00(t_lab, lab_of_hex(p.hex))
                return MatchResult("exact", target.hex, [p], None, d, None,
                                   f"Use {p.name} ({p.code}).")

    # Single-match pool is same-finish only
    ranked = _nearest_first(t_lab, [p for p in owned if p.finish == target.finish])
    nearest_single_d = delta_e00(t_lab, lab_of_hex(ranked[0].hex)) if ranked else float("inf")
    if ranked:
        nearest = ranked[0]
        d0 = nearest_single_d
        # Tier 1b: exact by near-zero distance
        if d0 <= EXACT_THRESHOLD:
            return MatchResult("exact", target.hex, [nearest], None, d0, None,
                               f"Use {nearest.name} ({nearest.code})." if nearest.code
                               else f"Use {nearest.name}.")
        # Tier 2: close single
        if d0 <= CLOSE_THRESHOLD:
            dev = _deviation(t_lab, lab_of_hex(nearest.hex))
            return MatchResult("close", target.hex, [nearest], None, d0, None,
                               f"Closest you own: {nearest.name} — {dev} (ΔE {d0:.1f}).")

    # Tier 3: mix (2 or 3 paints), finish-legal, ΔE-gated
    mixes = _candidate_mixes(t_lab, owned, target.finish)
    best2 = min((m for m in mixes if len(m[0]) == 2), key=lambda m: m[2], default=None)
    best3 = min((m for m in mixes if len(m[0]) == 3), key=lambda m: m[2], default=None)

    def _ok(m) -> bool:
        return m is not None and m[2] <= MIX_ACCEPT_THRESHOLD and m[2] < nearest_single_d

    chosen = best2 if _ok(best2) else None
    if _ok(best3) and (best2 is None or best3[2] <= best2[2] - TRIPLE_IMPROVE_MARGIN):
        chosen = best3
    if chosen is not None:
        paints, parts, d = chosen
        return MatchResult("mix", target.hex, paints, parts, d, None,
                           _mix_phrase(paints, parts, target.finish))

    # Tier 4: unreachable + buy hint from same-finish catalogue
    owned_codes = {p.code for p in owned if p.code}
    unowned = [p for p in catalog if p.finish == target.finish and p.code not in owned_codes]
    buy = min(unowned, key=lambda p: delta_e00(t_lab, lab_of_hex(p.hex))) if unowned else None
    nearest = ranked[0] if ranked else None
    d_near = nearest_single_d if ranked else float("nan")
    phrase = "Can't match with what you own"
    if nearest:
        phrase += f" (nearest {nearest.name}, ΔE {d_near:.1f})"
    if buy:
        phrase += f". Or buy {buy.name}."
    return MatchResult("unreachable", target.hex, [nearest] if nearest else [], None,
                       d_near, buy, phrase)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_matching.py -q`
Expected: PASS — new finish/3-paint cases green, and all pre-existing cases (`test_normalizers`, `test_exact_*`, `test_close_*`, `test_mix_when_between_two_owned`, `test_mix_rejected_when_single_is_closer`, `test_unreachable_gives_buy_hint`, `test_target_from_paint`) still green (matte defaults preserve their behaviour).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/matching.py tests/test_matching.py
git commit -m "feat: finish-aware matching + bounded 2-3 paint mix engine (linear-light, ΔE-gated)"
```

---

### Task 4: Flag-based consistency caveats (`consistency.py`)

Switch the paint-type caveat from name-sniffing to the real `finish` flag, keeping the keyword sniff only as a fallback for finish-less custom paints.

**Files:**
- Modify: `src/mini_highlight_advisor/consistency.py:20-28` (`_paint_type_caveat`)
- Test: `tests/test_consistency.py` (add)

**Interfaces:**
- Consumes: `PaintColor.finish`.
- Produces: no signature change; `annotate` / `_paint_type_caveat` behaviour now finish-driven.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_consistency.py`:

```python
def test_metallic_caveat_by_finish_flag():
    res = _res(paints=[PaintColor("Sterling Silver", "#d5d7d6", finish="metallic")])
    note = annotate(res, role="Base")
    assert "stir" in note.lower() or "settle" in note.lower()


def test_wash_caveat_by_finish_flag():
    res = _res(paints=[PaintColor("Some Shade", "#405060", finish="wash")])
    note = annotate(res, role="Base")
    assert "flow" in note.lower() or "one pass" in note.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_consistency.py -q`
Expected: FAIL — a `finish="metallic"` paint named "Sterling Silver" happens to keyword-match today, but `finish="wash"` named "Some Shade" does not, so `test_wash_caveat_by_finish_flag` fails.

- [ ] **Step 3: Rewrite `_paint_type_caveat`**

Replace `_paint_type_caveat` in `src/mini_highlight_advisor/consistency.py` with:

```python
def _paint_type_caveat(paints: list[PaintColor]) -> str:
    finishes = {getattr(p, "finish", "matte") for p in paints}
    if "metallic" in finishes:
        return "Metallic: stir often, settles."
    if "wash" in finishes or "contrast" in finishes:
        return "Flows: one pass."
    # Fallback keyword sniff for finish-less / custom paints.
    blob = " ".join(f"{p.name} {p.paint_range or ''}" for p in paints).lower()
    if any(k in blob for k in _METALLIC):
        return "Metallic: stir often, settles."
    if any(k in blob for k in _LOW_OPACITY):
        return "Low opacity: expect extra coats."
    if any(k in blob for k in _FLOW):
        return "Flows: one pass."
    return ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_consistency.py -q`
Expected: PASS — new cases green; existing cases (`test_metallic_caveat` via keyword fallback, `test_low_opacity_caveat`, etc.) still green.

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/consistency.py tests/test_consistency.py
git commit -m "feat: consistency caveats keyed on finish flag (keyword fallback retained)"
```

---

### Task 5: Catalogue metallic curation + full regression + app smoke

Tag the real metallics across all ranges in `vallejo_paints.json`, leave matte entries and the keyword false-positives untouched, then run the whole suite and hand the live app to the user. `app.py` needs **no code change** — finish already flows through `target_from_paint`.

**Files:**
- Modify: `src/mini_highlight_advisor/data/vallejo_paints.json` (add `"finish": "metallic"` to real metallics)
- Test: `tests/test_catalog.py` (add curation assertions)

**Interfaces:**
- Consumes: `catalog.load_catalog`, `catalog.find_by_code`.
- Produces: no code symbols — a data change locked by tests.

- [ ] **Step 1: Write the failing curation tests**

Append to `tests/test_catalog.py`:

```python
def test_known_metallics_tagged_after_curation():
    from mini_highlight_advisor.catalog import load_catalog, find_by_code
    cat = load_catalog()
    # TMM range + real metallics hiding in Model/Game Color
    for code in ["77.101", "70.997", "70.865", "72.052", "72.054", "72.055", "72.059"]:
        p = find_by_code(cat, code)
        assert p is not None and p.finish == "metallic", code


def test_colour_named_paints_stay_matte():
    from mini_highlight_advisor.catalog import load_catalog, find_by_code
    cat = load_catalog()
    # keyword false-positives that are NOT metallic paints — must remain matte
    for code in ["72.007", "72.036", "72.002", "70.897", "72.045"]:
        p = find_by_code(cat, code)
        assert p is not None and p.finish == "matte", code


def test_all_tmm_entries_are_metallic():
    from mini_highlight_advisor.catalog import load_catalog
    cat = load_catalog()
    tmm = [p for p in cat if p.paint_range == "True Metallic Metal"]
    assert tmm and all(p.finish == "metallic" for p in tmm)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_catalog.py -q`
Expected: FAIL — entries currently carry no `finish`, so they default to `matte`.

- [ ] **Step 3: List the metallic candidates to review**

Run this to print every keyword-candidate for a human decision:

```bash
.venv/Scripts/python -c "import json,re; d=json.load(open('src/mini_highlight_advisor/data/vallejo_paints.json',encoding='utf-8')); kw=re.compile(r'silver|gold|bronze|brass|copper|steel|gunmetal|chrome|tin|metal|iron|platinum|mithril|chainmail', re.I); [print(p['code'], p['range'], p['name']) for p in d['paints'] if kw.search(p['name']) or p['range']=='True Metallic Metal']"
```

- [ ] **Step 4: Tag the real metallics in the JSON**

Add `"finish": "metallic"` to each entry below (and to **every** `"range": "True Metallic Metal"` entry). These are genuine metallic paints:

- Model Color: `70.800` Gunmetal Blue, `70.865` Oily Steel, `70.863` Gunmetal Grey, `70.997` Silver, `70.878` Old Gold.
- Game Color: `72.052` Mithril Silver, `72.053` Chainmail Silver, `72.054` Gunmetal, `72.055` Polished Gold, `72.056` Glorious Gold, `72.057` Bright Bronze, `72.058` Brassy Brass, `72.059` Hammered Copper, `72.060` Tinny Tin.
- All 80 `True Metallic Metal` entries (`77.101`–`77.180`).

**Do NOT tag these** — they are matte colours whose *names* merely contain a metal word: `72.007` Gold Yellow, `72.002` White Gold, `72.036` Bronze Fleshtone, `70.897` Bronze Green.

Example edit (add the key before the closing brace of each metallic entry):

```json
{"code": "70.997", "name": "Silver", "brand": "Vallejo", "range": "Model Color", "hex": "#c9cccd", "finish": "metallic"},
```

- [ ] **Step 5: Run the curation tests + full suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: PASS — curation tests green; nothing else regressed. If `test_colour_named_paints_stay_matte` fails, you tagged a false-positive; if `test_known_metallics_tagged_after_curation` fails, you missed one of the codes in Step 4.

- [ ] **Step 6: Confirm the app still parses, then hand off the live smoke**

Run: `.venv/Scripts/python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read()); print('ok')"`
Expected: `ok`.

Then hand to the user (per project convention, do not self-run Streamlit):
> "Run `streamlit run app.py`. Build a palette with a **metallic** slot (pick e.g. Sterling Silver or Mithril Silver) and confirm the 'Match to my paints' advice only suggests metallics / a metallic + minority tint for that slot, never a matte-into-metallic mix — and that a matte slot never suggests a metallic. Confirm 3-paint mixes appear only where a pair genuinely can't reach the colour."

- [ ] **Step 7: Commit**

```bash
git add src/mini_highlight_advisor/data/vallejo_paints.json tests/test_catalog.py
git commit -m "data: tag metallic paints across ranges; lock curation with tests"
```

---

## Self-Review

**Spec coverage:**
- `finish` field on `PaintColor` (matte/metallic/wash/contrast, default matte) → Task 1. ✅
- Catalogue load + validate `finish`, default-on-load → Task 1. ✅
- `Target.finish`, inherited via `target_from_paint`, matte for ad-hoc/recipe → Task 3. ✅
- Same-finish single/close/nearest + buy-hint → Task 3 (`ranked` pool, `unowned` filter). ✅
- Matte target: matte-only mix, no metallic, wash/contrast excluded → Task 3 (`_candidate_mixes` matte branch; wash/contrast return empty). ✅
- Metallic target: all-metallic or metallic + minority tint → Task 3 (metallic branch + `_METAL_TINT_RATIOS`; `_mix_phrase` "tint"). ✅
- Bounded search: top-K=8 base, top-T=4 tints → Task 3 (`MIX_TOPK`, `MIX_TINT_TOPT`). ✅
- Coprime ratios summing ≤ 4 → Task 3 (`_ratios`). ✅
- Linear-light blend, still labelled approx → Task 2 (`linear_blend`) + Task 3 (`_mix_delta`, `_mix_phrase`). ✅
- 2-paint beats nearest single; 3-paint beats best 2-paint by ΔE ≥ 1.0, ≤ threshold → Task 3 (`_ok`, `TRIPLE_IMPROVE_MARGIN`). ✅
- Consistency caveat by finish flag with keyword fallback → Task 4. ✅
- Catalogue curation across all 244 (metallics in matte ranges tagged; colour-name false-positives left matte) → Task 5. ✅
- No new UI selectors; finish flows through existing `target_from_paint` → Task 5 Step 6 (app parse + smoke, no code change). ✅
- Data caveat (invented TMM codes / redundant ramps) — non-blocking, recorded in the spec; no task required. ✅

**Placeholder scan:** No TBD/TODO. Every code and test step is concrete. Task 5's JSON edit lists exact codes to tag and exact codes to leave alone. ✅

**Type consistency:** `PaintColor(..., finish="matte")` trailing field consistent across Tasks 1/3/4/5. `Target(hex, preferred_code, finish)` consistent between Task 3 def and its tests. `MatchResult` shape unchanged; `paints`/`parts` hold ≤3 entries. `linear_blend(rgbs, parts)` signature matches its Task 3 call site `_mix_delta`. Constants match the Global Constraints block verbatim. ✅

**Sequencing:** Task 1 → 2 → 3 → 4 → 5 is strict (3 imports `linear_blend` from 2 and `finish` from 1; 4 uses `finish` from 1; 5's tests need `finish` from 1). Boundary-sensitive tests in Task 3 carry an explicit "nudge the test hex, not the constant" note.
