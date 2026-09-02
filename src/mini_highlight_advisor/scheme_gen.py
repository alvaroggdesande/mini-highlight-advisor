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
