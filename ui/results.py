"""Results panel: match-to-paints, edge/relief/norm toggles, photo-quality, analyze & steps."""
import streamlit as st

from mini_highlight_advisor.matching import target_from_paint, target_from_hex
from mini_highlight_advisor.advisor import advise
from mini_highlight_advisor.palette import role_names
from mini_highlight_advisor.input_check import check_input, SHOOTING_GUIDE, PAINTED_CAPTURE_NOTE
from mini_highlight_advisor.pipeline import analyze_regions
from mini_highlight_advisor.overlay import swatch_board
from ui import context, helpers, keys


def render(rgb, alpha, book, palette, picked, owned_paints, shading,
           light_field=None, normal_field=None) -> None:
    ps_mode = light_field is not None
    # --- Match to my paints (scoped to this region's palette) ---
    st.markdown("#### Match to my paints")
    match_targets = [target_from_paint(p) for p in palette]
    match_roles = role_names(len(palette))
    adhoc = st.color_picker("Ad-hoc colour", value="#808080", key=keys.ADHOC_HEX)
    if st.checkbox("Include ad-hoc colour", key=keys.ADHOC_ON):
        match_targets = match_targets + [target_from_hex(adhoc)]
        match_roles = match_roles + ["Ad-hoc"]
    if not owned_paints:
        st.info("Tick the paints you own (Paints tab) to get match suggestions.")
    else:
        for row in advise(match_targets, match_roles, owned_paints, context.CATALOG):
            r = row.result
            chips = "".join(helpers.swatch(p.hex) for p in r.paints)
            st.markdown(f"{chips} **{row.role}** — {r.phrase}", unsafe_allow_html=True)
            if row.note:
                st.caption(row.note)

    st.divider()
    st.markdown("**Edge highlights**")
    edges = st.checkbox("Edge highlights", value=True, key=keys.EDGE_HL)
    extreme_edge = st.checkbox("Extreme edge highlight", value=False,
                               key=keys.EDGE_EXTREME, disabled=not edges)
    edge_sensitivity = st.slider("Edge sensitivity", 0.0, 1.0, 0.5, 0.05,
                                 key=keys.EDGE_SENS, disabled=not edges,
                                 help="Few sharpest edges (left) to more edges (right).")

    shades = False
    if normal_field is not None:
        shades = st.checkbox(
            "Recess shades", value=False, key=keys.SHADES,
            help="Darken concave recesses (creases, cavities) from the surface "
                 "normals — the inverse of edge highlights. PS mode only; reuses "
                 "the edge-sensitivity slider.")

    relief_cap = st.checkbox(
        "Auto-reduce bands on flat regions", value=True, key=keys.RELIEF_CAP,
        help="A flat region can't show every highlight band — cap it to what the "
             "relief supports. Untick to force your full band count everywhere.")

    if ps_mode:
        per_region_norm = False
    else:
        per_region_norm = st.checkbox(
            "Colored / painted mini (experimental)", value=False, key=keys.PER_REGION_NORM,
            help="Normalize brightness per region so each painted colour reads its own "
                 "relief. Off = primed-mini mode (default). Needs one lassoed region per "
                 "material; very dark regions may be flagged as too low-contrast to read.")

    # --- Photo quality panel (non-blocking, photo mode only) ---
    # `shading.mask` is the mask computed (and cached) by `helpers.shading()` above —
    # it is the same mask by value that `analyze_regions` will use; reusing it here
    # adds no extra depth-model run.
    if not ps_mode:
        try:
            st.subheader("\U0001F4F7 Photo quality")
            for r in check_input(rgb, shading.mask):
                line = f"**{r.label}** — {r.detail}"
                (st.success if r.ok else st.warning)(line)
            st.caption(PAINTED_CAPTURE_NOTE)
            with st.expander("How to photograph your mini"):
                st.markdown(SHOOTING_GUIDE)
        except Exception:
            st.caption("Photo-quality check unavailable for this image.")

    st.divider()
    wp, wcov, drawn = book.analyze_args()
    multi = analyze_regions(rgb, alpha, wp, wcov, drawn,
                            edges=edges, extreme_edge=extreme_edge,
                            edge_sensitivity=edge_sensitivity,
                            relief_cap=relief_cap,
                            per_region_norm=per_region_norm,
                            light_field=light_field,
                            normal_field=normal_field,
                            shades=shades)
    st.image(multi.combined_rgb, caption="Combined painted preview (all regions)",
             use_container_width=True)
    st.subheader("Colour schemes — all regions")
    st.image(swatch_board([(p.name, p.colors) for p in multi.plans]))
    st.subheader("Paint-along steps by region")
    st.caption("Work dark to light within each region.")
    for plan in multi.plans:
        st.markdown(f"### {plan.name}")
        if plan.flat_albedo:
            st.warning(
                f"“{plan.name}” is too dark / low-contrast to read relief — showing "
                f"1 band. Try a paler basecoat here, or a stronger raking side light. "
                f"(Single-photo tools can’t recover form from a dark, flat colour.)")
        elif plan.capped:
            st.warning(
                f"“{plan.name}” looks fairly flat — showing {len(plan.names)} "
                f"band(s) instead of {plan.requested_bands}. Untick "
                f"“Auto-reduce bands on flat regions” to force all "
                f"{plan.requested_bands}.")
        helpers.render_region_steps(plan.steps, plan.roles, plan.names, plan.coverage)
