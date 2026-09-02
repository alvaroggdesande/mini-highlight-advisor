"""Results panel: technique controls and paint-along steps."""
import streamlit as st

from mini_highlight_advisor.overlay import swatch_board
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
        st.slider("Horizon height", 0.0, 1.0, 0.5, 0.05, key=keys.NMM_HORIZON,
                  help="Slide the virtual NMM horizon up or down.")

    st.checkbox("Auto-reduce bands on flat regions", value=True, key=keys.RELIEF_CAP,
                help="Cap band count to what the relief supports.")

    if not has_normals:
        st.checkbox("Colored / painted mini (experimental)", value=False,
                    key=keys.PER_REGION_NORM,
                    help="Normalize brightness per region so each painted colour reads its "
                         "own relief. Off = primed-mini mode (default).")


def render_steps(multi) -> None:
    """Paint tab: swatch board + per-region paint-along steps.

    Call this from the Paint tab, reading keys.LAST_MULTI from session state.
    `multi` is None before the first analysis run; shows a placeholder then.
    """
    if multi is None:
        st.info("Set your colours in Studio first, then come here to paint.")
        return
    st.image(swatch_board([(p.name, p.colors) for p in multi.plans]),
             caption="Colour schemes - all regions")
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
