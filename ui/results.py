"""Results panel: technique controls and paint-along steps."""
import io
import streamlit as st

from mini_highlight_advisor.overlay import swatch_board, nmm_env_preview
from mini_highlight_advisor import materials, pipeline
from ui import helpers, keys


def render_technique_controls(book, sel: int, has_normals: bool) -> None:
    """Render technique, edge, relief, and photo-quality controls.

    Writes widget values into session_state. Does NOT call analyze_regions.
    Call this from the Technique sub-tab; read the values via helpers.run_analysis().
    """
    st.markdown("**Edge highlights**")
    st.checkbox("Edge highlights", value=True, key=keys.EDGE_HL)
    st.checkbox("Extreme edge highlight", value=False, key=keys.EDGE_EXTREME,
                disabled=not st.session_state.get(keys.EDGE_HL, True))
    st.slider("Edge sensitivity", 0.0, 1.0, 0.5, 0.05, key=keys.EDGE_SENS,
              disabled=not st.session_state.get(keys.EDGE_HL, True),
              help="Few sharpest edges (left) to more edges (right).")

    if has_normals:
        st.checkbox("Recess shades", value=False, key=keys.SHADES,
                    help="Darken concave recesses from surface normals (PS mode only).")

    # Technique picker
    cur_material = book.material_at(sel)
    cur_key = "smooth" if cur_material == "matte" else cur_material
    technique_labels = ["Smooth layering", "Drybrush"]
    technique_keys   = ["smooth",          "drybrush"]
    if has_normals:
        technique_labels.append("NMM")
        technique_keys.append("nmm")
    cur_idx = technique_keys.index(cur_key) if cur_key in technique_keys else 0
    choice_label = st.selectbox(
        f"Technique — {book.names()[sel]}", technique_labels, index=cur_idx,
        key=keys.material(sel),
        help=("Smooth layering: thin glazes, dark to light.\n"
              "Drybrush: drag a nearly-dry brush across raised surfaces.\n"
              "NMM (PS mode only): non-metallic metal from surface normals."),
    )
    chosen_key = technique_keys[technique_labels.index(choice_label)]
    book.set_material_at(sel, chosen_key)

    if has_normals and chosen_key == "nmm":
        st.markdown("**Metal environment** (the world your metal reflects)")
        preset = st.selectbox("Preset", ["Steel", "Gold", "Chrome", "Custom"],
                              key=keys.NMM_PRESET)
        if preset != "Custom":
            knobs = materials.NMM_PRESETS[preset]
        else:
            knobs = dict(horizon=0.5, light_dir=135.0, bounce=0.35, hotspot=0.5)
        nmm_horizon = st.slider("Horizon height", 0.0, 1.0, knobs["horizon"], 0.05,
                                key=keys.NMM_HORIZON,
                                help="Where the sky/ground break sits on the reflection.")
        nmm_light_dir = st.slider("Light direction", 0.0, 360.0, knobs["light_dir"], 5.0,
                                  key=keys.NMM_LIGHT_DIR,
                                  help="Azimuth of the reflected light streak/glint "
                                       "(90=top, 135=upper-left).")
        st.slider("Metal smoothing", 0.0, 8.0, 2.0, 0.5,
                  key=keys.NMM_SMOOTH,
                  help="Blurs the surface normals before the reflection lookup. "
                       "Raw PS normals are noisy; 1.5-3 gives coherent metal zones. "
                       "0 = off (raw, speckly).")
        with st.expander("Custom / advanced"):
            nmm_bounce = st.slider("Ground bounce", 0.0, 1.0, knobs["bounce"], 0.05,
                                   key=keys.NMM_BOUNCE)
            nmm_hotspot = st.slider("Hotspot", 0.0, 1.0, knobs["hotspot"], 0.05,
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
        st.image(preview, caption="Where each colour goes (reflected environment)",
                 width=180)

    st.checkbox("Auto-reduce bands on flat regions", value=True, key=keys.RELIEF_CAP,
                help="Cap band count to what the relief supports.")

    if not has_normals:
        st.checkbox("Colored / painted mini (experimental)", value=False,
                    key=keys.PER_REGION_NORM,
                    help="Normalize brightness per region so each painted colour reads its "
                         "own relief. Off = primed-mini mode (default).")


def render_osl_steps(osl_result) -> None:
    """Render the object-source glow paint-along steps.

    No-op when osl_result is None or has no steps. Call this right after
    render_steps() in the Paint tab to show OSL glazing layers.
    """
    if osl_result is None or not osl_result.steps:
        return
    st.subheader("Object-source glow — extra steps")
    st.caption("Paint the object normally first, then glaze the glow on top.")
    n = len(osl_result.steps)
    for i, s in enumerate(osl_result.steps):
        cols = st.columns(2)
        cols[0].image(s.zone_rgb,
                      caption=pipeline.osl_step_caption(i, n, s.label),
                      use_container_width=True)
        cols[1].image(s.cumulative_rgb, caption="after this layer",
                      use_container_width=True)


def render_steps(multi) -> None:
    """Paint tab: swatch board + per-region paint-along steps.

    Call this from the Paint tab, reading keys.LAST_MULTI from session state.
    `multi` is None before the first analysis run; shows a placeholder then.
    """
    if multi is None:
        st.info("Set your colours in Studio first, then come here to paint.")
        return
    board_img = swatch_board([(p.name, p.colors) for p in multi.plans])
    st.image(board_img, caption="Colour schemes - all regions")
    buf = io.BytesIO()
    board_img.save(buf, format="PNG")
    st.download_button("⬇ Download swatch board", buf.getvalue(),
                       file_name="swatch_board.png", mime="image/png")
    st.subheader("Paint-along steps by region")
    st.caption("Work dark to light within each region.")
    for plan in multi.plans:
        st.markdown(f"### {plan.name}")
        if plan.flat_albedo:
            st.warning(
                f'"{plan.name}" is too dark / low-contrast to read relief - showing '
                f"1 band. Try a paler basecoat here, or a stronger raking side light.")
        elif plan.capped:
            st.warning(
                f'"{plan.name}" looks fairly flat - showing {len(plan.names)} '
                f'band(s) instead of {plan.requested_bands}. Untick '
                f'"Auto-reduce bands on flat regions" to force all '
                f"{plan.requested_bands}.")
        helpers.render_region_steps(plan.steps, plan.roles, plan.names, plan.coverage,
                                    technique=plan.technique)
