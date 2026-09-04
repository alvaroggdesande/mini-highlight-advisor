"""The shared Studio editor.

Given a shading source — an rgb image, its `ShadingResult`, and the optional
light/normal fields — plus a region book, this renders the painted preview, the
persistent region selector, and the Manage / Colour / Technique tabs. Both the
Photo path (`app.py`) and the PS import path (`ui/ps_mode.py`) call this, so the
two input modes share one editor implementation instead of drifting apart.

The caller owns everything upstream (input gate, angle switcher or relight
controls, how rgb + shading are produced) and everything mode-specific
downstream (photo mode's project save; PS mode is session-only). This function
is that shared middle.
"""
import streamlit as st

from ui import colour_panel, geometry, helpers, keys, regions_panel, results, state


def render(rgb, alpha, book, shading, *, light_field, normal_field,
           picked, owned_paints):
    """Render the editor for one shading source. Returns the MultiRegionResult.

    `alpha` is whatever the region pipeline should treat as coverage/alpha for
    this mode — the photo path passes the image alpha channel, PS passes the
    mask as uint8.
    """
    # Sync visibility toggles from session_state into the book BEFORE analysis.
    # The toggles render after analysis (they live in col_controls), so without
    # this pre-sync the preview would always be one rerun behind the toggles.
    for _g in range(len(book.names())):
        _vk = f"vis_{_g}"
        if _vk in st.session_state:
            book.set_blank_at(_g, not st.session_state[_vk])

    # Run analysis BEFORE the columns, reading the control values the user set on
    # the previous run (same as what the widgets currently display). This keeps
    # the left render in sync with the right-hand controls without an extra rerun.
    multi = helpers.run_analysis(rgb, alpha, book, shading,
                                 light_field=light_field, normal_field=normal_field)
    st.session_state[keys.LAST_MULTI] = multi
    st.session_state[keys.LAST_RGB] = rgb

    col_render, col_controls = st.columns([1, 1])

    with col_render:
        st.image(multi.combined_rgb,
                 caption="Painted preview (all regions)",
                 use_container_width=True)
        # Photo-quality checks only make sense for a real photo; PS supplies a
        # normal field, so this self-guards off for the import path.
        if normal_field is None:
            try:
                from mini_highlight_advisor.input_check import check_input
                checks = check_input(rgb, shading.mask)
                all_ok = all(r.ok for r in checks)
                label = "📷 Photo quality" if all_ok else "📷 Photo quality ⚠️"
                with st.expander(label, expanded=not all_ok):
                    for r in checks:
                        (st.success if r.ok else st.warning)(f"**{r.label}** — {r.detail}")
            except Exception:
                pass

    with col_controls:
        # Persistent region selector — visible across all tabs.
        src_h, src_w = rgb.shape[:2]
        labels = book.names()
        sel = st.radio(
            "Region to edit",
            list(range(len(labels))),
            index=min(book.selected, len(labels) - 1),
            format_func=lambda g: geometry.region_label(g, labels[g]),
            key=keys.REGION_RADIO,
            horizontal=True,
        )
        if book.drawn:
            vis_cols = st.columns(len(labels))
            for _g, (_col, _lbl) in enumerate(zip(vis_cols, labels)):
                _vis = _col.toggle(_lbl, value=not book.blank_at(_g), key=f"vis_{_g}")
                book.set_blank_at(_g, not _vis)
        state.load_region_into_widgets(book, sel)
        state.rehydrate_editor_widgets(book, sel)
        book.selected = sel

        has_normals = normal_field is not None
        subtab_m, subtab_c, subtab_t = st.tabs(["🗺 Manage", "🎨 Colour", "🖌 Technique"])

        with subtab_m:
            regions_panel.render_management(book, rgb, shading, src_w, src_h, sel)

        with subtab_c:
            colour_panel.render(book, sel, picked, owned_paints, rgb=rgb)

        with subtab_t:
            results.render_technique_controls(book, sel, has_normals=has_normals)

    return multi
