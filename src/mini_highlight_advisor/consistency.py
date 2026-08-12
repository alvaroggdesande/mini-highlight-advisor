# src/mini_highlight_advisor/consistency.py
from __future__ import annotations

from .matching import MatchResult
from .palette import PaintColor

ROLE_DILUTION = {
    "Shadow": "2 thin coats, milk-like.",
    "Base": "2 thin coats, milk-like.",
    "Midtone": "thinned more, build up gradually.",
    "Highlight": "thinned more, build up gradually.",
    "Bright Highlight": "thinned more, build up gradually.",
    "Edge Highlight": "thinned, fine controlled tip.",
    "Extreme Edge Highlight": "thinned, fine controlled tip.",
}

_METALLIC = ("metal", "steel", "gold", "silver", "bronze", "chrome", "gunmetal", "iron")
_LOW_OPACITY = ("white", "yellow")
_FLOW = ("ink", "wash", "contrast")


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
