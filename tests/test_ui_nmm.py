# tests/test_ui_nmm.py
from streamlit.testing.v1 import AppTest

# Mounts the real results.render() on the synthetic PS fixture, WITH the normal field
# (so NMM controls are capability-enabled).
HARNESS_PS = """
import numpy as np
from pathlib import Path
from PIL import Image
import streamlit as st
from mini_highlight_advisor import relight
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

FIX = Path("tests/fixtures/ps")
normals = relight.load_normals(str(FIX / "synth_normal.png"))
mask = np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127
lf, relit = relight.relight(normals, mask, relight.light_dir(225, 45))
mask_u8 = (mask * 255).astype(np.uint8)
book = new_book(5)
st.session_state[keys.BOOK] = book
picked, owned = [], []
wp, wcov, drawn = book.analyze_args()
results.render(relit, mask_u8, book, wp, picked, owned, None,
               light_field=lf, normal_field=normals)
st.write("ok")
"""

# Photo mode: no light field, no normal field -> NMM controls must be absent.
HARNESS_PHOTO = """
import numpy as np
from pathlib import Path
from PIL import Image
import streamlit as st
from mini_highlight_advisor import relight
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

FIX = Path("tests/fixtures/ps")
normals = relight.load_normals(str(FIX / "synth_normal.png"))
mask = np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127
_, relit = relight.relight(normals, mask, relight.light_dir(225, 45))
mask_u8 = (mask * 255).astype(np.uint8)
book = new_book(5)
st.session_state[keys.BOOK] = book
wp, wcov, drawn = book.analyze_args()
sh = type('S', (), {'mask': mask})()
results.render(relit, mask_u8, book, wp, [], [], sh)
st.write("ok")
"""


def test_ps_mode_shows_technique_selector_and_horizon_when_nmm():
    # Technique picker is visible in PS mode; horizon slider appears after NMM is chosen.
    at = AppTest.from_string(HARNESS_PS); at.run()
    assert not at.exception
    labels = [(s.label or "").lower() for s in at.selectbox]
    assert any("technique" in l for l in labels)
    # Select NMM, then horizon slider should appear.
    tech = next(s for s in at.selectbox if "technique" in (s.label or "").lower())
    tech.set_value("NMM").run()
    assert not at.exception
    slider_labels = [(s.label or "").lower() for s in at.slider]
    assert any("horizon" in l for l in slider_labels)


def test_ps_mode_selecting_nmm_replans_without_error():
    at = AppTest.from_string(HARNESS_PS); at.run()
    tech = next(s for s in at.selectbox if "technique" in (s.label or "").lower())
    tech.set_value("NMM").run()
    assert not at.exception
    assert len(at.image) > 0            # combined preview still renders


def test_photo_mode_shows_technique_but_hides_horizon():
    # Technique picker is always visible; NMM option and horizon slider are PS-only.
    at = AppTest.from_string(HARNESS_PHOTO); at.run()
    assert not at.exception
    labels = [(s.label or "").lower() for s in at.selectbox]
    assert any("technique" in l for l in labels)
    # NMM should not be an option in photo mode.
    tech = next(s for s in at.selectbox if "technique" in (s.label or "").lower())
    assert "NMM" not in tech.options
    # Horizon slider must not appear in photo mode.
    slider_labels = [(s.label or "").lower() for s in at.slider]
    assert not any("horizon" in l for l in slider_labels)
