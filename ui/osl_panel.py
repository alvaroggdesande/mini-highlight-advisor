"""PS-mode-only Object-Source Lighting panel: click-to-place a coloured glow.

Streamlit reruns on every interaction; the caller re-derives the glow from the
returned params. Returns None until the user places a source AND ticks 'Enable'.
"""
import numpy as np
import streamlit as st
from PIL import Image

from ui import keys
from ui.compat import st_canvas
from ui import geometry
from mini_highlight_advisor import palette

PRESETS = {  # (glow_rgb, hot_rgb)
    "Torch":  ((255, 150, 40), (255, 230, 190)),
    "Plasma": ((40, 200, 255), (210, 245, 255)),
    "Gem":    ((60, 220, 120), (210, 255, 225)),
}


def _hex_to_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def _rescale_click(click, disp_w, disp_h, src_w, src_h) -> tuple[float, float]:
    """Map a click on the display-scaled canvas back to full mask resolution."""
    sx, sy = src_w / disp_w, src_h / disp_h
    return float(click[0]) * sx, float(click[1]) * sy


def params_from_session(mask_shape) -> dict | None:
    """Assemble OSL params from session_state without drawing widgets.

    Returns None unless the glow is enabled AND a source point is placed.
    Mirrors the dict render() returns, reading the same keys the widgets write.
    """
    if not st.session_state.get(keys.OSL_ON):
        return None
    click = st.session_state.get(keys.OSL_POINT)
    if click is None:
        return None
    glow_hex = st.session_state.get(keys.OSL_GLOW) or '#%02x%02x%02x' % PRESETS["Torch"][0]
    hot_hex = st.session_state.get(keys.OSL_HOT) or '#%02x%02x%02x' % PRESETS["Torch"][1]
    n_layers = int(st.session_state.get(keys.OSL_LAYERS, 3))
    return {
        "x": float(click[0]), "y": float(click[1]),
        "height": float(st.session_state.get(keys.OSL_HEIGHT, 40.0)),
        "reach": float(st.session_state.get(keys.OSL_REACH, 60.0)),
        "intensity": float(st.session_state.get(keys.OSL_INTENSITY, 1.0)),
        "coverage": palette.default_coverage(n_layers),
        "glow_rgb": _hex_to_rgb(glow_hex), "hot_rgb": _hex_to_rgb(hot_hex),
    }


def render(mask_shape, background_rgb) -> dict | None:
    st.markdown("**Object-source glow** (OSL) — click where the light lives, pick a colour.")
    enabled = st.checkbox("Enable glow", value=st.session_state.get(keys.OSL_ON, False),
                          key=keys.OSL_ON)
    if not enabled:
        return None

    preset = st.selectbox("Preset", list(PRESETS), key=keys.OSL_PRESET)
    dg, dh = PRESETS[preset]
    glow_hex = st.color_picker("Glow colour", '#%02x%02x%02x' % dg, key=keys.OSL_GLOW)
    hot_hex = st.color_picker("Hotspot tint", '#%02x%02x%02x' % dh, key=keys.OSL_HOT)
    height = st.slider("Height (off surface)", 0.0, 120.0, 40.0, key=keys.OSL_HEIGHT)
    reach = st.slider("Reach (glow radius, px)", 5.0, 300.0, 60.0, key=keys.OSL_REACH)
    intensity = st.slider("Intensity", 0.1, 2.0, 1.0, key=keys.OSL_INTENSITY)
    n_layers = st.slider("Glow layers", 2, 4, 3, key=keys.OSL_LAYERS)

    st.caption("Click the source point on the mini below.")
    src_h, src_w = mask_shape
    disp_w = min(600, src_w)
    disp_h = round(src_h * disp_w / src_w)
    click = None
    if st_canvas is not None:
        canvas = st_canvas(
            background_image=Image.fromarray(background_rgb),
            height=disp_h, width=disp_w, drawing_mode="point",
            stroke_width=6, stroke_color="#ff28c8", key=keys.OSL_CANVAS,
        )
        raw = geometry.last_point(canvas)
        if raw is not None:
            click = _rescale_click(raw, disp_w, disp_h, src_w, src_h)
    if click is None:
        click = st.session_state.get(keys.OSL_POINT)
    if click is None:
        st.info("No source placed yet — click on the mini.")
        return None
    st.session_state[keys.OSL_POINT] = click

    return params_from_session(mask_shape)
