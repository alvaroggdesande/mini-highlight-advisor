"""Presentational + data helpers for the Streamlit UI."""
import os
import tempfile

import streamlit as st

from mini_highlight_advisor.masking import load_image
from mini_highlight_advisor.pipeline import prepare_shading
from mini_highlight_advisor.palette import default_coverage
from mini_highlight_advisor.techniques import get_technique
from mini_highlight_advisor import pipeline
from i18n import t
from ui import keys


# cache_resource (not cache_data): the decoded rgb/alpha and the ShadingResult are
# treated as read-only inputs everywhere downstream (analyze_regions builds fresh
# arrays; nothing writes back into these). cache_data deep-COPIES its return value
# on every call — a full multi-megapixel copy of rgb + alpha + mask + light on each
# rerun, cache hit or not. cache_resource hands back the same objects, so an
# unchanged photo costs nothing to re-serve.
@st.cache_resource(show_spinner=False)
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


def render_region_steps(steps, roles, names, coverage, technique: str = "smooth",
                        palette=None, picked=None) -> None:
    # Shared paint-along step renderer for both the single-palette and the
    # per-region plans. `coverage` is per-band realized percentages.
    # Edge steps (step.kind == "edge") are appended after tonal steps; their
    # index is >= len(roles), so we guard the roles/names lookup with step.label.
    # `palette` (list[PaintColor]) and `picked` (list of owned codes) are optional;
    # when present, ownership / match text is shown below each tonal step.
    _spec = get_technique(technique)
    _picked_set = set(picked) if picked else set()
    _owned_list = None   # built lazily only if a custom-colour match is needed
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
            if palette is not None and step.index < len(palette):
                paint = palette[step.index]
                if paint.code:
                    badge = t("colour.owned_badge") if paint.code in _picked_set else t("colour.not_owned_badge")
                    st.caption(f"{paint.hex} · {badge}")
                else:
                    from mini_highlight_advisor.matching import match, Target
                    from ui import context as _ctx
                    if _owned_list is None:
                        _owned_list = [p for p in _ctx.CATALOG if p.code and p.code in _picked_set]
                    _finish = "metallic" if technique == "nmm" else "matte"
                    _result = match(Target(paint.hex, None, _finish),
                                    owned=_owned_list, catalog=list(_ctx.CATALOG))
                    st.caption(_result.phrase)
        if step.is_last:
            c1, c2 = st.columns(2)
            c1.image(step.zone_rgb, caption=t("results.where_to_paint"), use_container_width=True)
            c2.image(step.cumulative_rgb,
                     caption=_spec.captions.across.format(pct=cum_cov),
                     use_container_width=True)
        else:
            c1, c2, c3 = st.columns(3)
            c1.image(step.zone_rgb, caption=t("results.where_to_paint"), use_container_width=True)
            c2.image(step.cumulative_rgb,
                     caption=_spec.captions.across.format(pct=cum_cov),
                     use_container_width=True)
            c3.image(step.exact_rgb,
                     caption=_spec.captions.stays.format(pct=cov),
                     use_container_width=True)


def _analysis_settings() -> tuple:
    """All session-state control values that feed analyze_regions, as a hashable
    tuple. Used both to pass the values and to build the memo signature."""
    return (
        st.session_state.get(keys.EDGE_HL, True),
        st.session_state.get(keys.EDGE_EXTREME, False),
        st.session_state.get(keys.EDGE_SENS, 0.5),
        st.session_state.get(keys.RELIEF_CAP, True),
        st.session_state.get(keys.PER_REGION_NORM, False),
        st.session_state.get(keys.SHADES, False),
        st.session_state.get(keys.NMM_HORIZON, 0.5),
        st.session_state.get(keys.NMM_LIGHT_DIR, 135.0),
        st.session_state.get(keys.NMM_BOUNCE, 0.35),
        st.session_state.get(keys.NMM_HOTSPOT, 0.5),
        st.session_state.get(keys.NMM_SMOOTH, 2.0),
    )


def _analysis_signature(rgb, alpha, book, settings, light_field, normal_field) -> tuple:
    """A hashable identity that changes iff the analysis result would change.

    Masks are never mutated in place (regions are immutable once drawn), so their
    object id is a cheap, exact fingerprint; palette/coverage/material ARE mutated,
    so those go in by value. rgb must be fingerprinted by CONTENT, not id():
    PS mode passes a freshly-relit rgb (a new array with identical content) on
    every rerun, so id(rgb) changes each rerun — content-keying is what lets the
    memo hit. (Photo-mode rgb is stable now that shading() is @st.cache_resource,
    but the content key stays correct there too.)"""
    wp, wcov, drawn = book.analyze_args()
    regions = tuple(
        (id(r.mask), tuple(p.hex for p in r.palette), tuple(r.coverage), r.material)
        for r in drawn
    )
    return (
        rgb.shape, hash(rgb.tobytes()),
        tuple(p.hex for p in wp), tuple(wcov),
        book.material_at(0), book.whole_blank,
        regions,
        id(light_field) if light_field is not None else None,
        id(normal_field) if normal_field is not None else None,
        settings,
    )


def run_analysis(rgb, alpha, book, shading,
                 light_field=None, normal_field=None):
    """Run analyze_regions reading all control values from session_state.

    Call this BEFORE rendering columns so the result is available for the
    left-column render in the same Streamlit pass.

    Memoized against a one-entry session cache keyed by an input signature: the
    Studio tab re-runs this on every Streamlit rerun (each lasso stroke, tab
    switch, or unrelated widget change), and the full banding/edge/relief pipeline
    is the dominant per-rerun cost. Unchanged inputs now return the cached result
    instead of recomputing.
    """
    from mini_highlight_advisor.pipeline import analyze_regions
    from ui import _profile

    settings = _analysis_settings()
    with _profile.prof("run_analysis: signature"):
        sig = _analysis_signature(rgb, alpha, book, settings, light_field, normal_field)
    if st.session_state.get("_analysis_sig") == sig:
        _profile.mark("run_analysis: HIT (skipped analyze_regions)")
        return st.session_state.get("_analysis_result")
    _profile.mark("run_analysis: MISS -> running analyze_regions")

    (edges, extreme_edge, edge_sensitivity, relief_cap, per_region_norm, shades,
     nmm_horizon, nmm_light_dir, nmm_bounce, nmm_hotspot, nmm_smooth) = settings

    wp, wcov, drawn = book.analyze_args()
    with _profile.prof("run_analysis: analyze_regions"):
        result = analyze_regions(
            rgb, alpha, wp, wcov, drawn,
            edges=edges, extreme_edge=extreme_edge,
            edge_sensitivity=edge_sensitivity,
            relief_cap=relief_cap,
            per_region_norm=per_region_norm,
            light_field=light_field,
            normal_field=normal_field,
            shades=shades,
            nmm_horizon=nmm_horizon,
            nmm_light_dir=nmm_light_dir,
            nmm_bounce=nmm_bounce,
            nmm_hotspot=nmm_hotspot,
            nmm_smooth=nmm_smooth,
            whole_material=book.material_at(0),
            whole_blank=book.whole_blank,
            shading=shading,
        )
    st.session_state["_analysis_sig"] = sig
    st.session_state["_analysis_result"] = result
    return result


def build_osl_result(combined_rgb, normals, mask, params, owned=None, catalog=None):
    """Composite the OSL glow onto combined_rgb and return (preview_rgb, OslResult).

    Streamlit-free so it is unit-testable. `params` is the dict from
    osl_panel.render, or None when the glow is disabled/unplaced — in which case
    the input image is returned unchanged and the result is None.
    """
    if params is None:
        return combined_rgb, None
    src = pipeline.OslSource(
        x=params["x"], y=params["y"], height=params["height"],
        glow_rgb=params["glow_rgb"], hot_rgb=params["hot_rgb"],
    )
    result = pipeline.apply_osl(
        combined_rgb, normals, mask, src,
        reach=params["reach"], intensity=params["intensity"],
        coverage=params["coverage"], owned=owned or [], catalog=catalog,
    )
    return result.preview_rgb, result
