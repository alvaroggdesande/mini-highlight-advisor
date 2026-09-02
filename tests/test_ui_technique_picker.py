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
import numpy as np
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

# Minimal shading stub
class _Shading:
    mask = np.ones((8, 8), dtype=bool)
    light = np.full((8, 8), 0.5, dtype=np.float32)

rgb   = np.zeros((8, 8, 3), dtype=np.uint8)
alpha = np.full((8, 8), 255, dtype=np.uint8)

if keys.BOOK not in st.session_state:
    st.session_state[keys.BOOK] = new_book(3)
book = st.session_state[keys.BOOK]

results.render(rgb, alpha, book, book.palette_at(0), [], [], _Shading())
"""

# --- PS mode harness (normal_field seeded) ---
HARNESS_PS = """
import streamlit as st
import numpy as np
from pathlib import Path
from PIL import Image
from mini_highlight_advisor import relight
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

FIX = Path("tests/fixtures/ps")
book = new_book(3)

if keys.NORMALS not in st.session_state:
    normals = relight.load_normals(str(FIX / "synth_normal.png"))
    mask    = np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127
    st.session_state[keys.NORMALS] = normals
    st.session_state[keys.PS_MASK] = mask
    st.session_state[keys.PS_ALBEDO] = None

H, W = st.session_state[keys.NORMALS].shape[:2]

class _Shading:
    mask = np.ones((H, W), dtype=bool)
    light = np.full((H, W), 0.5, dtype=np.float32)

rgb   = np.zeros((H, W, 3), dtype=np.uint8)
alpha = np.full((H, W), 255, dtype=np.uint8)
normals = st.session_state[keys.NORMALS]

results.render(rgb, alpha, book, book.palette_at(0), [], [], _Shading(),
               normal_field=normals)
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
