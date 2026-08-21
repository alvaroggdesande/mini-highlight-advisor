import os

import streamlit as st

from mini_highlight_advisor.region_state import RegionBook, new_book
from ui import context, coverage_editor, helpers, paints_tab, results, state, palette_editor, regions_panel


st.set_page_config(page_title="Mini Highlight Advisor", layout="wide")
st.title("Mini Highlight Advisor")
st.caption(
    "Upload a photo of a primed miniature (background-removed PNG is fastest). "
    "You'll get a painted preview + a paint-by-layer plan. Best with a raking "
    "side light (not on-axis flash) — that gives the sculpt the shadows the tool reads."
)



tab_mini, tab_paints = st.tabs(["🖌️ Miniature", "🎨 Paints"])

# NOTE: st.tabs runs BOTH bodies every rerun, in code order. Fill the Paints
# tab FIRST so owned_codes / owned_paints are finalised before the Miniature
# tab renders its ownership badges. Display order (Miniature first) is fixed by
# the label list above, not by code order — do not reorder the labels.

# --- 🎨 Paints tab: inventory ---
with tab_paints:
    picked, owned_paints = paints_tab.render()

# --- 🖌️ Miniature tab: region-centric editor ---
with tab_mini:
    if "book" not in st.session_state:
        st.session_state["book"] = new_book(5)
    book: RegionBook = st.session_state["book"]

    uploaded = st.file_uploader("Mini photo", type=["png", "jpg", "jpeg"])
    if uploaded is None:
        st.info("Upload a photo of a primed miniature to begin.")
        st.stop()

    suffix = os.path.splitext(uploaded.name)[1]
    try:
        with st.spinner("Preparing shading (first run downloads the depth model if no alpha channel)..."):
            rgb, alpha, shading = helpers.shading(uploaded.getvalue(), suffix)
        src_h, src_w = rgb.shape[:2]

        sel = regions_panel.render(book, rgb, shading, src_w, src_h)
        state.rehydrate_editor_widgets(book, sel)

        palette, n = palette_editor.render(book, sel, picked)

        coverage = coverage_editor.render(n)

        # --- Save current palette as a recipe ---
        palette_editor.render_save_recipe(palette, n)

        # Write the edited palette/coverage back into the book for the selected region.
        book.set_palette_at(sel, palette)
        book.set_coverage_at(sel, coverage)

        results.render(rgb, alpha, book, palette, picked, owned_paints, shading)
    except Exception as e:
        st.error("Error processing image — see traceback below.")
        st.exception(e)
