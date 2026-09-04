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
