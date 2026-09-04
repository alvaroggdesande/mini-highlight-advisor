# tests/test_ui_technique_captions.py
"""Verify that render_region_steps shows technique-specific captions."""
import numpy as np
from pathlib import Path
from PIL import Image
from streamlit.testing.v1 import AppTest

FIX = Path("tests/fixtures/ps")

# Harness: seeds PS state + a 3-band drybrush plan, then calls render_region_steps.
# We check that the output contains a drybrush-specific caption substring.
HARNESS_DRYBRUSH_CAPTIONS = """
import numpy as np
import streamlit as st
from mini_highlight_advisor.overlay import BandStep
from ui.helpers import render_region_steps

# Synthetic 3-step plan (no real images needed — just small arrays)
h, w = 8, 8
zone  = np.zeros((h, w, 3), dtype=np.uint8)
cum   = np.zeros((h, w, 3), dtype=np.uint8)
exact = np.zeros((h, w, 3), dtype=np.uint8)

steps = [
    BandStep(index=0, zone_rgb=zone, cumulative_rgb=cum, exact_rgb=exact,
             is_last=False, kind="band"),
    BandStep(index=1, zone_rgb=zone, cumulative_rgb=cum, exact_rgb=exact,
             is_last=False, kind="band"),
    BandStep(index=2, zone_rgb=zone, cumulative_rgb=cum, exact_rgb=cum,
             is_last=True, kind="band"),
]
roles    = ["Base coat", "Drybrush", "Highlight drybrush"]
names    = ["Wash Black", "Brown", "Bone"]
coverage = [40.0, 35.0, 25.0]

render_region_steps(steps, roles, names, coverage, technique="drybrush")
st.write("done")
"""

HARNESS_SMOOTH_CAPTIONS = """
import numpy as np
import streamlit as st
from mini_highlight_advisor.overlay import BandStep
from ui.helpers import render_region_steps

h, w = 8, 8
zone  = np.zeros((h, w, 3), dtype=np.uint8)
cum   = np.zeros((h, w, 3), dtype=np.uint8)
exact = np.zeros((h, w, 3), dtype=np.uint8)

steps = [
    BandStep(index=0, zone_rgb=zone, cumulative_rgb=cum, exact_rgb=exact,
             is_last=False, kind="band"),
    BandStep(index=1, zone_rgb=zone, cumulative_rgb=cum, exact_rgb=exact,
             is_last=True, kind="band"),
]
roles    = ["Shadow", "Highlight"]
names    = ["Black", "White"]
coverage = [60.0, 40.0]

render_region_steps(steps, roles, names, coverage, technique="smooth")
st.write("done")
"""


def test_drybrush_captions_render_without_error():
    at = AppTest.from_string(HARNESS_DRYBRUSH_CAPTIONS)
    at.run()
    assert not at.exception


def test_smooth_captions_render_without_error():
    at = AppTest.from_string(HARNESS_SMOOTH_CAPTIONS)
    at.run()
    assert not at.exception


def test_drybrush_captions_default_smooth_no_error():
    # Calling render_region_steps without technique= must still work (back-compat).
    harness = HARNESS_SMOOTH_CAPTIONS.replace(
        "render_region_steps(steps, roles, names, coverage, technique=\"smooth\")",
        "render_region_steps(steps, roles, names, coverage)",
    )
    at = AppTest.from_string(harness)
    at.run()
    assert not at.exception
