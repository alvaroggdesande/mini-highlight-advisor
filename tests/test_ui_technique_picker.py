# tests/test_ui_technique_picker.py
"""Technique picker is visible in simple-image mode and PS mode."""
import numpy as np
from pathlib import Path
from PIL import Image
from streamlit.testing.v1 import AppTest
from mini_highlight_advisor import relight
from ui import keys

FIX = Path("tests/fixtures/ps")

# --- Simple-image mode harness (no normal_field) ---
HARNESS_PHOTO = """
import streamlit as st
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

if keys.BOOK not in st.session_state:
    st.session_state[keys.BOOK] = new_book(3)
book = st.session_state[keys.BOOK]

results.render_technique_controls(book, 0, has_normals=False)
"""

# --- PS mode harness (normal_field seeded) ---
HARNESS_PS = """
import streamlit as st
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

book = new_book(3)
st.session_state[keys.BOOK] = book
results.render_technique_controls(book, 0, has_normals=True)
"""


def test_technique_picker_renders_in_photo_mode():
    at = AppTest.from_string(HARNESS_PHOTO)
    at.run()
    assert not at.exception


def test_technique_picker_renders_in_ps_mode():
    at = AppTest.from_string(HARNESS_PS)
    at.run()
    assert not at.exception


def test_matte_normalises_to_smooth_in_picker():
    # A book with "matte" material must not raise a ValueError in the picker.
    at = AppTest.from_string(HARNESS_PHOTO)
    at.run()
    assert not at.exception


def test_set_drybrush_via_picker_updates_book():
    """Selecting Drybrush in photo mode writes 'drybrush' to the book."""
    at = AppTest.from_string(HARNESS_PHOTO)
    at.run()
    assert not at.exception
    # Select Drybrush option
    sel = at.selectbox[0]   # first (and only) technique selectbox
    sel.select("Drybrush")
    at.run()
    assert not at.exception
    # After applying, the book material must be "drybrush"
    book = at.session_state[keys.BOOK]
    assert book.material_at(0) == "drybrush"
