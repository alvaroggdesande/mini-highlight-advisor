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
try:
    from streamlit_drawable_canvas import st_canvas
except Exception as e:  # import/version failure = spike FAIL -> use fallback widget
    st.error(f"import failed: {e!r}")
    st.stop()

bg = Image.fromarray(np.full((300, 300, 3), 120, np.uint8))
res = st_canvas(
    fill_color="rgba(255,40,200,0.25)", stroke_width=2, stroke_color="#ff28c8",
    background_image=bg, height=300, width=300, drawing_mode="polygon",
    key="spike",
)
if res.json_data is not None:
    objs = res.json_data.get("objects", [])
    st.write(f"objects: {len(objs)}")
    if objs:
        st.json(objs[-1])  # <- confirm the vertex key/shape parsed in Task 7
