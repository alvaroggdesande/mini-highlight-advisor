"""Regression tests for the angle bar (ui/angles_panel).

Guards the add-angle uploader against the "phantom angle" bug: st_canvas lasso
strokes trigger reruns on which the file_uploader transiently reports None; a
None-re-armable signature guard would then re-add the still-present file on the
next rerun, spawning a duplicate angle per stroke. The fix consumes each upload
exactly once via a nonce-rotated uploader key, so subsequent reruns cannot
re-add it. These tests drive the real render() through Streamlit's AppTest.
"""
from streamlit.testing.v1 import AppTest

# Minimal harness that mounts the real angles_panel.render(), plus a button that
# stands in for an st_canvas stroke (each click forces a rerun, like a stroke).
HARNESS = """
import streamlit as st
from ui import angles_panel, keys, state
from mini_highlight_advisor import projects
from mini_highlight_advisor.region_state import new_book

if keys.ANGLES not in st.session_state:
    _a = projects.AngleData(
        label="angle 1", photo_bytes=b"PB", photo_suffix=".png",
        book=new_book(5), settings=state._current_settings())
    st.session_state[keys.ANGLES] = [_a]
    st.session_state[keys.ACTIVE_ANGLE] = 0
    state.seed_editor_from_angle(_a)   # mirror app.py bootstrap (seeds keys.BOOK)

angles_panel.render()

if st.button("stroke", key="stroke_btn"):
    st.rerun()

st.write("n_angles", len(st.session_state[keys.ANGLES]))
"""


def _run():
    at = AppTest.from_string(HARNESS)
    at.run()
    return at


def test_starts_with_single_angle():
    at = _run()
    assert len(at.session_state["angles"]) == 1


def test_upload_adds_exactly_one_angle():
    at = _run()
    at.get("file_uploader")[0].upload("angle2.png", b"x" * 100, "image/png")
    at.run()
    assert len(at.session_state["angles"]) == 2
    # the uploader must have rotated to a fresh key (consume-once)
    assert at.get("file_uploader")[0].key != "add_angle_uploader_0"


def test_reruns_after_upload_do_not_spawn_phantom_angles():
    """The core regression: strokes (reruns) after an upload must not re-add."""
    at = _run()
    at.get("file_uploader")[0].upload("angle2.png", b"x" * 100, "image/png")
    at.run()
    assert len(at.session_state["angles"]) == 2
    for _ in range(5):
        at.button(key="stroke_btn").click()
        at.run()
        assert len(at.session_state["angles"]) == 2
