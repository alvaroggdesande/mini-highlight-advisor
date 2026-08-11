"""Spike: does streamlit-drawable-canvas run on this repo's Streamlit?

Run: streamlit run spikes/canvas_spike.py

PASS if: the canvas renders, freehand/polygon drawing works, and json_data
returns objects with a readable point list. Inspect the printed JSON of the
last object to confirm which key holds the vertices (Task 7's
`_points_from_object` must parse it): typically obj["path"] as
[["M",x,y],["L",x,y],...] for polygon/freehand.

Non-interactive gate already PASSED (2026-08-11): streamlit-drawable-canvas
0.9.3 installs and imports cleanly against streamlit 1.61.1 (no version
conflict). This spike only confirms the runtime draw + the JSON path shape.
"""
import numpy as np
import streamlit as st
from PIL import Image

st.title("drawable-canvas spike")


def _patch_image_to_url() -> None:
    # drawable-canvas 0.9.3 calls streamlit.elements.image.image_to_url, which
    # newer Streamlit moved to streamlit.elements.lib.image_utils (2nd arg is
    # now a layout_config whose only read attribute is .width). Re-expose an
    # adapter so the component runs. Mirrors the shim in app.py.
    import streamlit.elements.image as _si
    if hasattr(_si, "image_to_url"):
        return
    from types import SimpleNamespace
    from streamlit.elements.lib import image_utils as _iu

    def image_to_url(image, width, clamp, channels, output_format, image_id):
        return _iu.image_to_url(
            image, SimpleNamespace(width=width), clamp, channels, output_format, image_id
        )

    _si.image_to_url = image_to_url


_patch_image_to_url()

try:
    from streamlit_drawable_canvas import st_canvas
except Exception as e:  # import/version failure = spike FAIL -> use fallback widget
    st.error(f"import failed: {e!r}")
    st.stop()

bg = Image.fromarray(np.full((300, 300, 3), 120, np.uint8))
res = st_canvas(
    fill_color="rgba(255,40,200,0.25)", stroke_width=2, stroke_color="#ff28c8",
    background_image=bg, height=300, width=300, drawing_mode="freedraw",
    key="spike",
)
if res.json_data is not None:
    objs = res.json_data.get("objects", [])
    st.write(f"objects: {len(objs)}")
    if objs:
        st.json(objs[-1])  # <- confirm the vertex key/shape parsed in Task 7
