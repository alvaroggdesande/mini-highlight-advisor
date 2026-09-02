from streamlit.testing.v1 import AppTest

HARNESS_NONE = """
import streamlit as st
from ui import results
results.render_steps(None)
st.write("ok")
"""

HARNESS_MULTI = """
import numpy as np
from pathlib import Path
from PIL import Image
import streamlit as st
from mini_highlight_advisor import relight
from mini_highlight_advisor.masking import compute_mask
from mini_highlight_advisor.region_state import new_book
from mini_highlight_advisor.pipeline import analyze_regions
from ui import results, keys

FIX = Path("tests/fixtures/ps")
normals = relight.load_normals(str(FIX / "synth_normal.png"))
mask = np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127
lf, relit = relight.relight(normals, mask, relight.light_dir(225, 45))
mask_u8 = (mask * 255).astype(np.uint8)
book = new_book(5)
wp, wcov, drawn = book.analyze_args()
multi = analyze_regions(relit, mask_u8, wp, wcov, drawn, light_field=lf)
results.render_steps(multi)
st.write("ok")
"""

def test_render_steps_none_shows_placeholder():
    at = AppTest.from_string(HARNESS_NONE)
    at.run()
    assert not at.exception
    texts = [i.value for i in at.info]
    assert any("Studio" in t for t in texts)

def test_render_steps_with_multi_renders_images():
    at = AppTest.from_string(HARNESS_MULTI)
    at.run()
    assert not at.exception
    assert len(at.image) >= 1  # at least the swatch board
