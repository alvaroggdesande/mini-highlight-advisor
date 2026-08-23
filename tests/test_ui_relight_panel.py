from streamlit.testing.v1 import AppTest

HARNESS = """
import streamlit as st
from ui import relight_panel
az, el = relight_panel.render()
st.write("az", az)
st.write("el", el)
"""


def _run():
    at = AppTest.from_string(HARNESS)
    at.run()
    return at


def test_renders_two_sliders_with_defaults():
    at = _run()
    assert len(at.slider) == 2
    assert at.session_state["light_az"] is not None
    assert at.session_state["light_el"] is not None


def test_preset_button_sets_light():
    at = _run()
    # click the "Raking-L" preset; azimuth/elevation should jump to its values
    at.button(key="preset_Raking-L").click()
    at.run()
    assert at.session_state["light_az"] == 200
    assert at.session_state["light_el"] == 20
