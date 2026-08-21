"""Region-management panel: draw-mode canvas, region list, add/delete, rename.

Renders the left (canvas or outline preview) and right (radio + controls)
columns, plus the "### Editing" header and rename block below them.

Returns the selected region index (sel) so app.py can pass it on to
palette_editor and coverage_editor.
"""
import streamlit as st
from PIL import Image

from mini_highlight_advisor.regions import scale_points, polygons_to_mask
from mini_highlight_advisor.palette import default_ramp
from ui import geometry, helpers, keys, state
from ui.compat import st_canvas


def render(book, rgb, shading, src_w, src_h) -> int:
    """Render the region panel and return the selected region index."""
    disp_w = min(600, src_w)
    disp_h = round(src_h * disp_w / src_w)
    draw_mode = st.session_state.get(keys.DRAW_MODE, False)

    left, right = st.columns([3, 2])
    with left:
        # In draw mode the big left panel IS the drawing surface (st_canvas
        # needs a wide, un-nested container to render — it collapses inside a
        # narrow column/expander). Otherwise show the read-only outline preview.
        if draw_mode and st_canvas is not None:
            st.caption("Trace a lasso around an area below, then click **Add region** on the right.")
            canvas = st_canvas(
                fill_color="rgba(255,40,200,0.25)", stroke_width=2, stroke_color="#ff28c8",
                background_image=Image.fromarray(rgb), height=disp_h, width=disp_w,
                drawing_mode="freedraw", key=keys.canvas(len(book.drawn)),
            )
        else:
            canvas = None
            outline = geometry.region_outline_image(rgb, book.drawn)
            st.image(outline, caption="Preview (region outlines)", use_container_width=True)
    with right:
        st.markdown("**Regions**")
        labels = book.names()
        sel = st.radio(
            "Select a region to edit", list(range(len(labels))),
            index=min(book.selected, len(labels) - 1),
            format_func=lambda g: labels[g], key=keys.REGION_RADIO,
        )
        state.load_region_into_widgets(book, sel)
        book.selected = sel

        st.divider()
        if st_canvas is None:
            st.info("Install `streamlit-drawable-canvas` to draw regions.")
        elif not draw_mode:
            if st.button("➕ Draw a new region"):
                st.session_state[keys.DRAW_MODE] = True
                st.rerun()
        else:
            st.markdown("**New region** — lasso on the image, left.")
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

        if sel >= 1 and st.button("🗑 Delete this region"):
            book.remove(sel)
            st.session_state.pop(keys.LOADED_G, None)
            for _k in [k for k in list(st.session_state) if k.startswith(keys.RENAME_PREFIX)]:
                st.session_state.pop(_k, None)
            st.rerun()

    st.divider()
    st.markdown(f"### Editing: **{book.names()[sel]}**")

    # Rename the selected drawn region (Whole mini / index 0 is fixed).
    if sel >= 1:
        renamed = st.text_input("Region name", value=book.names()[sel], key=keys.rename(sel))
        if renamed.strip() and renamed.strip() != book.names()[sel]:
            book.set_name_at(sel, renamed)
            st.session_state.pop(keys.LOADED_G, None)
            st.rerun()

    return sel
