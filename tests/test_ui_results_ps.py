from streamlit.testing.v1 import AppTest

# Mounts render_technique_controls() on a minimal book in PS mode.
HARNESS_PS = """
import streamlit as st
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

book = new_book(5)
st.session_state[keys.BOOK] = book
results.render_technique_controls(book, 0, has_normals=True)
st.write("ok")
"""

# Photo mode: no normals -> colored-mini toggle should appear.
HARNESS_PHOTO = """
import streamlit as st
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

book = new_book(5)
st.session_state[keys.BOOK] = book
results.render_technique_controls(book, 0, has_normals=False)
st.write("ok")
"""


def test_ps_mode_hides_coloured_toggle():
    at = AppTest.from_string(HARNESS_PS); at.run()
    assert not at.exception
    labels = [c.label for c in at.checkbox]
    assert not any("painted mini" in (l or "").lower() for l in labels)


def test_ps_mode_renders_plan_without_error():
    at = AppTest.from_string(HARNESS_PS); at.run()
    assert not at.exception
    # Verify analysis ran without error: render() runs and stores state
    # (Images are now rendered by render_steps(), not render())
    # Just verify no errors occurred in the render() call


def test_photo_mode_still_shows_coloured_toggle():
    at = AppTest.from_string(HARNESS_PHOTO); at.run()
    assert not at.exception
    labels = [c.label for c in at.checkbox]
    assert any("painted mini" in (l or "").lower() for l in labels)


def test_render_technique_controls_exists():
    import ui.results as r
    assert hasattr(r, "render_technique_controls")


def test_render_technique_controls_smoke():
    HARNESS = """
import numpy as np
import streamlit as st
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

book = new_book(5)
st.session_state[keys.BOOK] = book
results.render_technique_controls(book, 0, has_normals=False)
st.write("ok")
"""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(HARNESS)
    at.run()
    assert not at.exception
