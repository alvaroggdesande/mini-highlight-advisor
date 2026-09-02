"""PS input branch: import a normal.png + mask.png bundle, relight under a global
virtual light, and drive the shared editor with the resulting light field.

Session-only (v1): no persistence, no multi-angle. Torch-free — ps_tool produced
the bundle out of process.
"""
import numpy as np
import streamlit as st
from PIL import Image

from mini_highlight_advisor import relight
from mini_highlight_advisor.masking import compute_mask
from mini_highlight_advisor.pipeline import ShadingResult
from mini_highlight_advisor.region_state import new_book
from ui import colour_panel, coverage_editor, helpers, keys, regions_panel, results, relight_panel, state


def _import_gate() -> bool:
    """Three uploaders (normal + mask required; albedo optional). Returns True
    once a valid bundle is in session."""
    if keys.NORMALS in st.session_state and keys.PS_MASK in st.session_state:
        return True
    st.info("Import a photometric-stereo bundle produced by `tools/ps_tool.py`: "
            "a normal map and its mask. See docs/ps-capture-guide.md.")
    c1, c2, c3 = st.columns(3)
    nrm = c1.file_uploader("normal.png", type=["png"], key="ps_upload_normal")
    msk = c2.file_uploader("mask.png", type=["png"], key="ps_upload_mask")
    alb = c3.file_uploader("albedo.png (optional)", type=["png"],
                           key="ps_upload_albedo")
    if nrm is None or msk is None:
        return False

    rgb01 = np.asarray(Image.open(nrm).convert("RGB"), np.float32) / 255.0
    mask = np.asarray(Image.open(msk).convert("L")) > 127
    if rgb01.shape[:2] != mask.shape:
        st.error(f"Dimension mismatch: normal {rgb01.shape[:2]} vs mask {mask.shape}. "
                 "The two files must be the same size.")
        return False
    if not relight.plausible_unit_normals(rgb01, mask):
        st.error("That doesn't look like a normal map (values don't decode to unit "
                 "normals over the mask). Re-export the bundle from ps_tool.")
        return False

    st.session_state[keys.NORMALS] = relight._decode(rgb01)
    st.session_state[keys.PS_MASK] = mask

    # Albedo is optional — absent or implausible → None (grey fallback)
    albedo = None
    if alb is not None:
        albedo_arr = relight.load_albedo(alb)
        if relight.plausible_albedo(albedo_arr, mask):
            albedo = albedo_arr
        else:
            st.warning("albedo.png didn't pass the plausibility check — "
                       "falling back to grey display base.")
    st.session_state[keys.PS_ALBEDO] = albedo

    st.rerun()
    return True


def render(picked, owned_paints) -> None:
    if not _import_gate():
        st.stop()

    normals = st.session_state[keys.NORMALS]
    mask = st.session_state[keys.PS_MASK]
    albedo = st.session_state.get(keys.PS_ALBEDO)   # None for old bundles

    az, el = relight_panel.render()
    light_field, relit_rgb = relight.relight(
        normals, mask, relight.light_dir(az, el), albedo=albedo)
    mask_u8 = (mask * 255).astype(np.uint8)
    shading = ShadingResult(mask=compute_mask(relit_rgb, mask_u8), light=light_field)

    # PS keeps its own book (keys.PS_BOOK): photo mode's keys.BOOK may hold regions
    # lassoed against a different-sized photo, which would break assign_owners when
    # applied to the PS mask. Keeping them separate isolates the two input modes.
    st.session_state.setdefault(keys.PS_BOOK, new_book(5))
    book = st.session_state[keys.PS_BOOK]

    # Run analysis before columns (standard pattern: uses session_state from previous run).
    multi = helpers.run_analysis(relit_rgb, mask_u8, book, shading,
                                 light_field=light_field, normal_field=normals)
    st.session_state[keys.LAST_MULTI] = multi
    st.session_state[keys.LAST_RGB] = relit_rgb

    col_render, col_controls = st.columns([1, 1])

    with col_render:
        st.image(multi.combined_rgb,
                 caption="Painted preview (all regions)",
                 use_container_width=True)

    with col_controls:
        sel = st.session_state.get(keys.REGION_RADIO, 0)
        subtab_r, subtab_c, subtab_t = st.tabs(["🗺 Regions", "🎨 Colour", "🖌 Technique"])

        with subtab_r:
            src_h, src_w = relit_rgb.shape[:2]
            sel = regions_panel.render(book, relit_rgb, shading, src_w, src_h)
            state.rehydrate_editor_widgets(book, sel)
            n = st.session_state.get(keys.N, 5)
            coverage = coverage_editor.render(n)
            book.set_coverage_at(sel, coverage)

        with subtab_c:
            colour_panel.render(book, sel, picked, owned_paints)

        with subtab_t:
            results.render_technique_controls(book, sel, has_normals=True)
