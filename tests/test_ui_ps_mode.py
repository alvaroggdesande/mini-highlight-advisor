import io
import numpy as np
from pathlib import Path
from PIL import Image
from streamlit.testing.v1 import AppTest

FIX = Path("tests/fixtures/ps")

# Pre-seeds an imported bundle in session (skips the uploader interaction), then
# drives ps_mode.render() end to end on the synthetic fixture.
HARNESS = """
import numpy as np
from pathlib import Path
from PIL import Image
import streamlit as st
from mini_highlight_advisor import relight
from ui import ps_mode, keys

FIX = Path("tests/fixtures/ps")
if keys.NORMALS not in st.session_state:
    st.session_state[keys.NORMALS] = relight.load_normals(str(FIX / "synth_normal.png"))
    st.session_state[keys.PS_MASK] = (
        np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127)

ps_mode.render(picked=[], owned_paints=[])
st.write("done")
"""


def test_ps_mode_shows_relight_panel_and_runs():
    at = AppTest.from_string(HARNESS); at.run()
    assert not at.exception
    # relight panel contributed the az/el sliders
    assert at.session_state["light_az"] is not None
    assert at.session_state["light_el"] is not None
    assert len(at.slider) >= 2


def test_moving_the_light_reruns_without_error():
    at = AppTest.from_string(HARNESS); at.run()
    at.slider(key="light_az").set_value(90).run()
    assert not at.exception
    assert at.session_state["light_az"] == 90


def test_ps_mode_geometry_wiring_runs():
    # PS mode now passes the session normals to analyze_regions as normal_field;
    # the full editor must render end-to-end on the synthetic fixture without error.
    at = AppTest.from_string(HARNESS); at.run()
    assert not at.exception
    assert at.session_state["ps_normals"] is not None


def test_ps_mode_recess_shades_toggle_runs():
    at = AppTest.from_string(HARNESS); at.run()
    assert not at.exception
    # the PS-only recess-shades checkbox is present...
    box = at.checkbox(key="shades")
    assert box is not None
    # ...and toggling it on re-runs the full editor without error.
    box.set_value(True).run()
    assert not at.exception
    assert at.session_state["shades"] is True
