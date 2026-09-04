"""PS-mode-only Object-Source Lighting panel: click-to-place a coloured glow.

Streamlit reruns on every interaction; the caller re-derives the glow from the
returned params. Returns None until the user places a source AND ticks 'Enable'.
"""
import numpy as np
import streamlit as st

from ui import keys
from ui.compat import st_canvas
from ui import geometry

PRESETS = {  # (glow_rgb, hot_rgb)
    "Torch":  ((255, 150, 40), (255, 230, 190)),
    "Plasma": ((40, 200, 255), (210, 245, 255)),
    "Gem":    ((60, 220, 120), (210, 255, 225)),
}


def _hex_to_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def render(mask_shape) -> dict | None:
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

    st.caption("Click the source point on the canvas below.")
    click = None
    if st_canvas is not None:
        h, w = mask_shape
        canvas = st_canvas(height=h, width=w, drawing_mode="point",
                           stroke_width=6, key=keys.OSL_CANVAS)
        click = geometry.last_point(canvas)
    if click is None:
        click = st.session_state.get(keys.OSL_POINT)
    if click is None:
        st.info("No source placed yet — click on the mini.")
        return None
    st.session_state[keys.OSL_POINT] = click

    x, y = float(click[0]), float(click[1])
    return {
        "x": x, "y": y, "height": float(height), "reach": float(reach),
        "intensity": float(intensity), "coverage": [1.0] * int(n_layers),
        "glow_rgb": _hex_to_rgb(glow_hex), "hot_rgb": _hex_to_rgb(hot_hex),
    }
