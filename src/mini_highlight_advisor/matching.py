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

    # Tier 3: mix — only when it beats the nearest single owned paint
    mix = _best_mix(t_lab, owned) if len(owned) >= 2 else None
    nearest_single_d = delta_e00(t_lab, lab_of_hex(ranked[0].hex)) if ranked else float("inf")
    if mix and mix[3] <= MIX_ACCEPT_THRESHOLD and mix[3] < nearest_single_d:
        a, b, parts, d = mix
        return MatchResult("mix", target.hex, [a, b], parts, d, None,
                           f"Mix ~{parts[0]}:{parts[1]} {a.name} + {b.name} (approx).")

    # Tier 4: unreachable + buy hint from full catalogue
    unowned = [p for p in catalog if p not in owned]
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
