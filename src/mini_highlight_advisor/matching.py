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
    # A valid triple beats an invalid/absent pair even without the margin improvement.
    if _ok(best3) and (best2 is None or best3[2] <= best2[2] - TRIPLE_IMPROVE_MARGIN):
        chosen = best3
    if chosen is not None:
        paints, parts, d = chosen
        return MatchResult("mix", target.hex, paints, parts, d, None,
                           _mix_phrase(paints, parts, target.finish))

    # Tier 4: unreachable + buy hint from same-finish catalogue
    owned_set = set(owned)
    owned_codes = {p.code for p in owned if p.code}
    unowned = [
        p for p in catalog
        if p.finish == target.finish
        and p not in owned_set
        and (not p.code or p.code not in owned_codes)
    ]
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
