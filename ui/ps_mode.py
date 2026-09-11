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
from ui import editor, keys, relight_panel


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
    # Return (don't st.stop) so app.py's script pass continues to the later
    # 🪜 Paint / 🖼️ All angles / 📷 Capture tab bodies. Before a bundle is
    # imported there's nothing to paint, but the Capture & help tab (holding the
    # PS capture guide) must still render.
    if not _import_gate():
        return

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

    # Seed OSL session keys from a loaded project's persisted OSL params (if any)
    # whenever the OSL keys have not yet been set this session.  Mirrors the
    # seed_editor_from_angle pattern in ui/state.py for all other settings keys.
    _active_idx = st.session_state.get(keys.ACTIVE_ANGLE, 0)
    _angles = st.session_state.get(keys.ANGLES, [])
    if _angles and _active_idx < len(_angles):
        _saved_osl = getattr(_angles[_active_idx].settings, "osl", None)
        if _saved_osl and not st.session_state.get(keys.OSL_ON):
            st.session_state.setdefault(keys.OSL_ON, True)
            if "x" in _saved_osl and "y" in _saved_osl:
                st.session_state.setdefault(keys.OSL_POINT,
                                            (_saved_osl["x"], _saved_osl["y"]))
            if "glow" in _saved_osl:
                st.session_state.setdefault(keys.OSL_GLOW, _saved_osl["glow"])
            if "hot" in _saved_osl:
                st.session_state.setdefault(keys.OSL_HOT, _saved_osl["hot"])
            if "height" in _saved_osl:
                st.session_state.setdefault(keys.OSL_HEIGHT, _saved_osl["height"])
            if "reach" in _saved_osl:
                st.session_state.setdefault(keys.OSL_REACH, _saved_osl["reach"])
            if "intensity" in _saved_osl:
                st.session_state.setdefault(keys.OSL_INTENSITY, _saved_osl["intensity"])
            if "layers" in _saved_osl:
                st.session_state.setdefault(keys.OSL_LAYERS, _saved_osl["layers"])

    # The shared editor renders preview + region selector + Manage/Colour/Technique.
    # PS is session-only, so (unlike the photo path) there is no project save call.
    # The editor now owns OSL (Glow tab) and stores keys.OSL_RESULT in session state.
    editor.render(relit_rgb, mask_u8, book, shading,
                  light_field=light_field, normal_field=normals,
                  picked=picked, owned_paints=owned_paints)
