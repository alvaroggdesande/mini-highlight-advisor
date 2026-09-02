"""Presentational + data helpers for the Streamlit UI."""
import os
import tempfile

import streamlit as st

from mini_highlight_advisor.masking import load_image
from mini_highlight_advisor.pipeline import prepare_shading
from mini_highlight_advisor.palette import default_coverage
from mini_highlight_advisor.techniques import get_technique
from ui import keys


@st.cache_data(show_spinner=False)
def shading(image_bytes: bytes, suffix: str):
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name
    try:
        rgb, alpha = load_image(tmp_path)
    finally:
        os.unlink(tmp_path)
    return rgb, alpha, prepare_shading(rgb, alpha)


def swatch(hexv: str, size: str = "1em") -> str:
    return (
        f"<span style='display:inline-block;width:{size};height:{size};"
        f"background-color:{hexv};border:1px solid #888;"
        f"vertical-align:middle;margin-right:0.5em'></span>"
    )


def current_cov_seed(n: int) -> list[float]:
    return [round(f * 100, 1) for f in default_coverage(n)]


def render_region_steps(steps, roles, names, coverage, technique: str = "smooth") -> None:
    # Shared paint-along step renderer for both the single-palette and the
    # per-region plans. `coverage` is per-band realized percentages.
    # Edge steps (step.kind == "edge") are appended after tonal steps; their
    # index is >= len(roles), so we guard the roles/names lookup with step.label.
    _spec = get_technique(technique)
    for step in steps:
        if step.label:
            # Edge step — label is set ("Edge Highlight" / "Extreme Edge Highlight")
            caption_text = step.label
            name_text = step.label
            cum_cov = 0.0
            cov = 0.0
            st.markdown(f"**Step {step.index + 1} — {step.label}**")
        else:
            caption_text = roles[step.index]
            name_text = names[step.index]
            cum_cov = sum(coverage[step.index:])
            cov = coverage[step.index]
            st.markdown(f"**Step {step.index + 1} — {caption_text} · {name_text}**")
        if step.is_last:
            c1, c2 = st.columns(2)
            c1.image(step.zone_rgb, caption="Where to paint", use_container_width=True)
            c2.image(step.cumulative_rgb,
                     caption=_spec.captions.across.format(pct=cum_cov),
                     use_container_width=True)
        else:
            c1, c2, c3 = st.columns(3)
            c1.image(step.zone_rgb, caption="Where to paint", use_container_width=True)
            c2.image(step.cumulative_rgb,
                     caption=_spec.captions.across.format(pct=cum_cov),
                     use_container_width=True)
            c3.image(step.exact_rgb,
                     caption=_spec.captions.stays.format(pct=cov),
                     use_container_width=True)


def run_analysis(rgb, alpha, book, shading,
                 light_field=None, normal_field=None):
    """Run analyze_regions reading all control values from session_state.

    Call this BEFORE rendering columns so the result is available for the
    left-column render in the same Streamlit pass.
    """
    from mini_highlight_advisor.pipeline import analyze_regions

    edges = st.session_state.get(keys.EDGE_HL, True)
    extreme_edge = st.session_state.get(keys.EDGE_EXTREME, False)
    edge_sensitivity = st.session_state.get(keys.EDGE_SENS, 0.5)
    relief_cap = st.session_state.get(keys.RELIEF_CAP, True)
    per_region_norm = st.session_state.get(keys.PER_REGION_NORM, False)
    shades = st.session_state.get(keys.SHADES, False)
    nmm_horizon = st.session_state.get(keys.NMM_HORIZON, 0.5)

    wp, wcov, drawn = book.analyze_args()
    return analyze_regions(
        rgb, alpha, wp, wcov, drawn,
        edges=edges, extreme_edge=extreme_edge,
        edge_sensitivity=edge_sensitivity,
        relief_cap=relief_cap,
        per_region_norm=per_region_norm,
        light_field=light_field,
        normal_field=normal_field,
        shades=shades,
        nmm_horizon=nmm_horizon,
        whole_material=book.material_at(0),
    )
