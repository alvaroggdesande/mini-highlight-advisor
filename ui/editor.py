"""The shared region -> palette -> coverage -> results editor body.

Extracted verbatim from app.py so photo mode and PS mode drive the SAME editor.
`light_field` is None for photo mode (luminance path) and a (H,W) float32 field
for PS mode (relit path).
"""
import streamlit as st

from ui import coverage_editor, palette_editor, regions_panel, results, state


def render_editor(rgb, alpha, shading, book, picked, owned_paints, light_field=None) -> None:
    src_h, src_w = rgb.shape[:2]
    sel = regions_panel.render(book, rgb, shading, src_w, src_h)
    state.rehydrate_editor_widgets(book, sel)

    palette, n = palette_editor.render(book, sel, picked)
    coverage = coverage_editor.render(n)
    palette_editor.render_save_recipe(palette, n)

    book.set_palette_at(sel, palette)
    book.set_coverage_at(sel, coverage)

    results.render(rgb, alpha, book, palette, picked, owned_paints, shading,
                   light_field=light_field)
