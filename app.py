import os
from pathlib import Path

import streamlit as st

from mini_highlight_advisor import projects
from mini_highlight_advisor.region_state import RegionBook, new_book
from ui import (
    angles_panel, colour_panel, coverage_editor, gallery_panel, helpers, keys,
    paints_tab, projects_panel, ps_mode, regions_panel, results, state,
)

st.set_page_config(page_title="Mini Highlight Advisor", layout="wide")
st.title("Mini Highlight Advisor")
st.caption(
    "Upload a photo of a primed miniature (background-removed PNG is fastest). "
    "You'll get a painted preview + a paint-by-layer plan. Best with a raking "
    "side light (not on-axis flash) — that gives the sculpt the shadows the tool reads."
)

# NOTE: st.tabs runs ALL bodies every rerun in code order.
# Paints must execute before Studio so owned_codes is finalised before Studio
# renders ownership badges. Display order is fixed by the label list.
tab_studio, tab_paint, tab_paints, tab_angles, tab_capture = st.tabs([
    "🖌️ Studio", "🪜 Paint", "🎨 Paints", "🖼️ All angles", "📷 Capture & help",
])

# --- 🎨 Paints: inventory (must run first — see note above) ---
with tab_paints:
    picked, owned_paints = paints_tab.render()

# --- 🖌️ Studio: visualise and decide ---
with tab_studio:
    st.session_state.setdefault(keys.ANGLES, [])
    st.session_state.setdefault(keys.ACTIVE_ANGLE, 0)

    projects_panel.render_library()

    input_mode = st.radio(
        "Input", ["Photo", "Import normal map (photometric stereo)"],
        horizontal=True, key="input_mode",
        help="Photo = primed mini under a raking light (luminance). PS = import a "
             "recovered normal map for dark/primed minis; drag a virtual light.")
    if input_mode.startswith("Import"):
        ps_mode.render(picked, owned_paints)
        st.stop()

    angles = st.session_state[keys.ANGLES]

    if not angles:
        uploaded = st.file_uploader("Mini photo", type=["png", "jpg", "jpeg"])
        if uploaded is None:
            st.info("Upload a photo of a primed miniature to begin, or load a saved project above.")
            st.stop()
        a = projects.AngleData(label="angle 1", photo_bytes=uploaded.getvalue(),
                               photo_suffix=os.path.splitext(uploaded.name)[1],
                               book=new_book(5), settings=state._current_settings())
        st.session_state[keys.ANGLES] = [a]
        state.set_active_angle(0)
        state.seed_editor_from_angle(a)
        st.rerun()

    active_idx = angles_panel.render()
    active = st.session_state[keys.ANGLES][active_idx]
    book = st.session_state[keys.BOOK]
    photo_bytes, photo_suffix = active.photo_bytes, active.photo_suffix

    try:
        with st.spinner("Preparing shading…"):
            rgb, alpha, shading = helpers.shading(photo_bytes, photo_suffix)

        normal_field = st.session_state.get(keys.NORMALS)
        light_field = None  # photo mode; PS mode takes a different branch above

        # Run analysis BEFORE columns using session_state from the previous run.
        # (Session_state holds the values the user set on the previous run, which
        # are the same as what the widgets currently display. This keeps the left
        # render in sync with the controls without an extra rerun.)
        multi = helpers.run_analysis(rgb, alpha, book, shading,
                                     light_field=light_field, normal_field=normal_field)
        st.session_state[keys.LAST_MULTI] = multi
        st.session_state[keys.LAST_RGB] = rgb

        col_render, col_controls = st.columns([1, 1])

        with col_render:
            st.image(multi.combined_rgb,
                     caption="Painted preview (all regions)",
                     use_container_width=True)
            # Compact photo-quality check
            if normal_field is None:
                try:
                    from mini_highlight_advisor.input_check import check_input
                    for r in check_input(rgb, shading.mask):
                        (st.success if r.ok else st.warning)(f"**{r.label}** — {r.detail}")
                except Exception:
                    pass

        with col_controls:
            subtab_r, subtab_c, subtab_t = st.tabs(["🗺 Regions", "🎨 Colour", "🖌 Technique"])

            with subtab_r:
                src_h, src_w = rgb.shape[:2]
                sel = regions_panel.render(book, rgb, shading, src_w, src_h)
                state.rehydrate_editor_widgets(book, sel)
                n = st.session_state.get(keys.N, 5)
                coverage = coverage_editor.render(n)
                book.set_coverage_at(sel, coverage)

            with subtab_c:
                colour_panel.render(book, sel, picked, owned_paints)

            with subtab_t:
                has_normals = normal_field is not None
                results.render_technique_controls(book, sel, has_normals=has_normals)

        projects_panel.render_save()

    except Exception as e:
        st.error("Error processing image — see traceback below.")
        st.exception(e)

# --- 🪜 Paint: paint-along steps ---
with tab_paint:
    multi = st.session_state.get(keys.LAST_MULTI)
    results.render_steps(multi)

# --- 🖼️ All angles: read-only gallery ---
with tab_angles:
    _angles = st.session_state.get(keys.ANGLES, [])
    _active = st.session_state.get(keys.ACTIVE_ANGLE, 0)
    if _angles:
        _angles[_active] = state.flush_editor_into_angle(_angles[_active])
    gallery_panel.render(_angles, _active)

# --- 📷 Capture & help ---
with tab_capture:
    from mini_highlight_advisor.input_check import SHOOTING_GUIDE, PAINTED_CAPTURE_NOTE
    st.header("How to photograph your mini")
    st.markdown(SHOOTING_GUIDE)
    st.divider()
    st.markdown(PAINTED_CAPTURE_NOTE)
    st.header("Photometric stereo (PS) capture")
    ps_guide = Path("docs/ps-capture-guide.md")
    if ps_guide.exists():
        st.markdown(ps_guide.read_text(encoding="utf-8"))
    else:
        st.caption("PS capture guide not found.")
