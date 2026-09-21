"""Results panel: technique controls and paint-along steps."""
import io
import streamlit as st

from mini_highlight_advisor.overlay import swatch_board, nmm_env_preview
from mini_highlight_advisor import materials, pipeline
from i18n import t
from ui import helpers, keys


def render_technique_controls(book, sel: int, has_normals: bool) -> None:
    """Render technique, edge, relief, and photo-quality controls.

    Writes widget values into session_state. Does NOT call analyze_regions.
    Call this from the Technique sub-tab; read the values via helpers.run_analysis().
    """
    st.markdown(t("results.edge_heading"))
    st.checkbox(t("results.edge_cb"), value=True, key=keys.EDGE_HL)
    st.checkbox(t("results.extreme_edge_cb"), value=False, key=keys.EDGE_EXTREME,
                disabled=not st.session_state.get(keys.EDGE_HL, True))
    st.slider(t("results.edge_sens_label"), 0.0, 1.0, 0.5, 0.05, key=keys.EDGE_SENS,
              disabled=not st.session_state.get(keys.EDGE_HL, True),
              help=t("results.edge_sens_help"))

    if has_normals:
        st.checkbox(t("results.recess_cb"), value=False, key=keys.SHADES,
                    help=t("results.recess_help"))

    # Technique picker
    cur_material = book.material_at(sel)
    cur_key = "smooth" if cur_material == "matte" else cur_material
    technique_labels = [t("results.technique_smooth"), t("results.technique_drybrush")]
    technique_keys   = ["smooth",                      "drybrush"]
    if has_normals:
        technique_labels.append(t("results.technique_nmm"))
        technique_keys.append("nmm")
    cur_idx = technique_keys.index(cur_key) if cur_key in technique_keys else 0
    choice_label = st.selectbox(
        t("results.technique_label", name=book.names()[sel]), technique_labels, index=cur_idx,
        key=keys.material(sel),
        help=t("results.technique_help"),
    )
    chosen_key = technique_keys[technique_labels.index(choice_label)]
    book.set_material_at(sel, chosen_key)

    if has_normals and chosen_key == "nmm":
        st.markdown(t("results.nmm_env_heading"))
        _nmm_preset_keys = ["Steel", "Gold", "Chrome", "Custom"]
        _nmm_preset_labels = {
            "Steel": t("results.nmm_preset_steel"),
            "Gold": t("results.nmm_preset_gold"),
            "Chrome": t("results.nmm_preset_chrome"),
            "Custom": t("results.nmm_preset_custom"),
        }
        preset = st.selectbox(t("results.nmm_preset_label"), _nmm_preset_keys,
                              format_func=lambda k: _nmm_preset_labels[k],
                              key=keys.NMM_PRESET)
        if preset != "Custom":
            knobs = materials.NMM_PRESETS[preset]
        else:
            knobs = dict(horizon=0.5, light_dir=135.0, bounce=0.35, hotspot=0.5)
        nmm_horizon = st.slider(t("results.horizon_label"), 0.0, 1.0, knobs["horizon"], 0.05,
                                key=keys.NMM_HORIZON,
                                help=t("results.horizon_help"))
        nmm_light_dir = st.slider(t("results.light_dir_label"), 0.0, 360.0, knobs["light_dir"], 5.0,
                                  key=keys.NMM_LIGHT_DIR,
                                  help=t("results.light_dir_help"))
        st.slider(t("results.smoothing_label"), 0.0, 8.0, 2.0, 0.5,
                  key=keys.NMM_SMOOTH,
                  help=t("results.smoothing_help"))
        with st.expander(t("results.custom_expander")):
            nmm_bounce = st.slider(t("results.bounce_label"), 0.0, 1.0, knobs["bounce"], 0.05,
                                   key=keys.NMM_BOUNCE)
            nmm_hotspot = st.slider(t("results.hotspot_label"), 0.0, 1.0, knobs["hotspot"], 0.05,
                                    key=keys.NMM_HOTSPOT)
        env = materials.build_nmm_env(
            horizon=nmm_horizon,
            light_dir=nmm_light_dir,
            bounce=st.session_state.get(keys.NMM_BOUNCE, knobs["bounce"]),
            hotspot=st.session_state.get(keys.NMM_HOTSPOT, knobs["hotspot"]),
        )
        steps = len(book.coverage_at(sel))
        preview = nmm_env_preview(env, [p.rgb for p in book.palette_at(sel)],
                                  n_bands=steps)
        st.image(preview, caption=t("results.env_preview_caption"), width=180)

    st.checkbox(t("results.relief_cap_cb"), value=True, key=keys.RELIEF_CAP,
                help=t("results.relief_cap_help"))

    if not has_normals:
        st.checkbox(t("results.coloured_mini_cb"), value=False,
                    key=keys.PER_REGION_NORM,
                    help=t("results.coloured_mini_help"))


def render_osl_steps(osl_result) -> None:
    """Render the object-source glow paint-along steps.

    No-op when osl_result is None or has no steps. Call this right after
    render_steps() in the Paint tab to show OSL glazing layers.
    """
    if osl_result is None or not osl_result.steps:
        return
    st.subheader(t("results.osl_steps_subheader"))
    st.caption(t("results.osl_steps_caption"))
    n = len(osl_result.steps)
    for i, s in enumerate(osl_result.steps):
        cols = st.columns(2)
        cols[0].image(s.zone_rgb,
                      caption=pipeline.osl_step_caption(i, n, s.label),
                      use_container_width=True)
        cols[1].image(s.cumulative_rgb, caption=t("results.after_layer_caption"),
                      use_container_width=True)


def render_steps(multi, key: str = "dl_swatch") -> None:
    """Paint tab: swatch board + per-region paint-along steps.

    Call this from the Paint tab, reading keys.LAST_MULTI from session state.
    `multi` is None before the first analysis run; shows a placeholder then.
    Pass a unique `key` when rendering multiple angles in the same script pass
    (e.g. inside st.tabs) to avoid duplicate-element-ID errors.
    """
    if multi is None:
        st.info(t("results.no_result_info"))
        return
    from ui import _profile
    with _profile.prof("PAINT tab: render_steps (all images)"):
        _render_steps_body(multi, key)


def _render_steps_body(multi, key: str = "dl_swatch") -> None:
    board_img = swatch_board([(p.name, p.colors) for p in multi.plans])
    st.image(board_img, caption=t("results.swatch_caption"))
    buf = io.BytesIO()
    board_img.save(buf, format="PNG")
    st.download_button(t("results.download_swatch_btn"), buf.getvalue(),
                       file_name="swatch_board.png", mime="image/png",
                       key=key)
    st.subheader(t("results.steps_subheader"))
    st.caption(t("results.steps_caption"))
    for plan in multi.plans:
        st.markdown(f"### {plan.name}")
        if plan.flat_albedo:
            st.warning(t("results.too_dark_warning", name=plan.name))
        elif plan.capped:
            st.warning(t("results.flat_warning", name=plan.name,
                          n=len(plan.names), requested=plan.requested_bands))
        helpers.render_region_steps(plan.steps, plan.roles, plan.names, plan.coverage,
                                    technique=plan.technique)
