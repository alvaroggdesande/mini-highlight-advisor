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
