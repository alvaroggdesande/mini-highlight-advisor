import os

import streamlit as st

from mini_highlight_advisor import projects
from mini_highlight_advisor.region_state import RegionBook, new_book
from ui import (
    angles_panel, editor, gallery_panel, helpers, keys, paints_tab,
    projects_panel, ps_mode, schemes_panel, state,
)

st.set_page_config(page_title="Mini Highlight Advisor", layout="wide")
st.title("Mini Highlight Advisor")
st.caption(
    "Upload a photo of a primed miniature (background-removed PNG is fastest). "
    "You'll get a painted preview + a paint-by-layer plan. Best with a raking "
    "side light (not on-axis flash) — that gives the sculpt the shadows the tool reads."
)

tab_mini, tab_paints, tab_gallery = st.tabs(["🖌️ Miniature", "🎨 Paints", "🖼️ All angles"])

# NOTE: st.tabs runs BOTH bodies every rerun, in code order. Fill the Paints
# tab FIRST so owned_codes / owned_paints are finalised before the Miniature
# tab renders its ownership badges. Display order (Miniature first) is fixed by
# the label list above, not by code order — do not reorder the labels.

# --- 🎨 Paints tab: inventory ---
with tab_paints:
    picked, owned_paints = paints_tab.render()

# --- 🖌️ Miniature tab: region-centric editor ---
with tab_mini:
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
        with st.spinner("Preparing shading (first run downloads the depth model if no alpha channel)..."):
            rgb, alpha, shading = helpers.shading(photo_bytes, photo_suffix)

        editor.render_editor(rgb, alpha, shading, book, picked, owned_paints)

        schemes_panel.render()
        projects_panel.render_save()
    except Exception as e:
        st.error("Error processing image — see traceback below.")
        st.exception(e)

# --- 🖼️ All angles tab: read-only combined gallery ---
# Runs AFTER the Miniature editor so it sees the active angle's live edits. When
# there are no angles the editor above st.stop()s the run, so this stays empty.
with tab_gallery:
    _angles = st.session_state.get(keys.ANGLES, [])
    _active = st.session_state.get(keys.ACTIVE_ANGLE, 0)
    if _angles:
        # reflect the active angle's unsaved edits (settings + live book) in its cell
        _angles[_active] = state.flush_editor_into_angle(_angles[_active])
    gallery_panel.render(_angles, _active)
