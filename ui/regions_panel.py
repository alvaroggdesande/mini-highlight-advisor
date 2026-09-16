"""Manage tab: draw, rename, delete, and blank-toggle regions.

The region selector (radio) now lives in app.py above the tabs so it's
persistent across all tabs. This module handles management-only actions for
the currently selected region.
"""
import streamlit as st
from PIL import Image

from mini_highlight_advisor.regions import scale_points, polygons_to_mask
from mini_highlight_advisor.palette import default_ramp
from ui import geometry, helpers, keys, state
from ui.compat import st_canvas


def render_management(book, rgb, shading, src_w, src_h, sel: int) -> None:
    """Render the Manage tab content for the selected region index."""
    disp_w = min(600, src_w)
    disp_h = round(src_h * disp_w / src_w)
    draw_mode = st.session_state.get(keys.DRAW_MODE, False)

    if draw_mode and st_canvas is not None:
        st.caption("Trace a lasso around an area below, then click **Add region**.")
        bg = geometry.region_outline_image(rgb, book.drawn)
        # Key the canvas by the active angle too: st_canvas persists its strokes by
        # widget key, so two angles with the same drawn-region count would otherwise
        # share one canvas and leak angle 1's lasso onto angle 2 (and vice-versa).
        angle_idx = st.session_state.get(keys.ACTIVE_ANGLE, 0)
        canvas = st_canvas(
            fill_color="rgba(255,40,200,0.25)", stroke_width=2, stroke_color="#ff28c8",
            background_image=Image.fromarray(bg), height=disp_h, width=disp_w,
            drawing_mode="freedraw", key=keys.canvas(angle_idx, len(book.drawn)),
        )
    else:
        canvas = None
        outline = geometry.region_outline_image(rgb, book.drawn)
        st.image(outline, caption="Region outlines", width=disp_w)

    st.divider()

    if st_canvas is None:
        st.info("Install `streamlit-drawable-canvas` to draw regions.")
    elif not draw_mode:
        if st.button("➕ Draw a new region"):
            st.session_state[keys.DRAW_MODE] = True
            st.rerun()
    else:
        st.markdown("**New region** — lasso on the image above.")
        new_name = st.text_input("Region name", value=f"Region {len(book.drawn) + 1}")
        c_add, c_cancel = st.columns(2)
        if c_add.button("Add region", type="primary"):
            objs = (canvas.json_data or {}).get("objects", []) if canvas else []
            if not objs:
                st.warning("Trace a lasso around an area on the image first.")
            else:
                sx, sy = src_w / disp_w, src_h / disp_h
                rings = [scale_points(geometry.points_from_object(o), sx, sy) for o in objs]
                rmask = polygons_to_mask(rings, (src_h, src_w)) & shading.mask
                if not rmask.any():
                    st.warning("Lasso didn't overlap the mini — trace around a part of the model.")
                else:
                    book.add(rmask, new_name.strip() or f"Region {len(book.drawn) + 1}",
                             default_ramp(st.session_state[keys.N]),
                             [c / 100 for c in helpers.current_cov_seed(st.session_state[keys.N])])
                    st.session_state.pop(keys.LOADED_G, None)
                    for _k in [k for k in list(st.session_state) if k.startswith(keys.RENAME_PREFIX)]:
                        st.session_state.pop(_k, None)
                    st.session_state[keys.DRAW_MODE] = False
                    st.rerun()
        if c_cancel.button("Cancel"):
            st.session_state[keys.DRAW_MODE] = False
            st.rerun()

    # Per-region controls for the selected region (hidden while drawing)
    if not draw_mode and sel >= 1:
        st.divider()
        renamed = st.text_input("Rename region", value=book.names()[sel],
                                key=keys.rename(sel))
        if renamed.strip() and renamed.strip() != book.names()[sel]:
            book.set_name_at(sel, renamed)
            st.session_state.pop(keys.LOADED_G, None)
            st.rerun()

        if st.button("🗑 Delete this region", key="delete_region_btn"):
            book.remove(sel)
            st.session_state.pop(keys.LOADED_G, None)
            for _k in [k for k in list(st.session_state) if k.startswith(keys.RENAME_PREFIX)]:
                st.session_state.pop(_k, None)
            st.rerun()
