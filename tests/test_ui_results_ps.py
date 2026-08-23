from streamlit.testing.v1 import AppTest

# Mounts the real results.render() on the synthetic PS fixture, in PS mode.
HARNESS_PS = """
import numpy as np
from pathlib import Path
from PIL import Image
import streamlit as st
from mini_highlight_advisor import relight
from mini_highlight_advisor.masking import compute_mask
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
palette = wp
results.render(relit, mask_u8, book, palette, picked, owned, None, light_field=lf)
st.write("ok")
"""

HARNESS_PHOTO = HARNESS_PS.replace(
    "results.render(relit, mask_u8, book, palette, picked, owned, None, light_field=lf)",
    "sh = type('S', (), {'mask': mask})()\n"
    "results.render(relit, mask_u8, book, palette, picked, owned, sh)",
)


def test_ps_mode_hides_coloured_toggle():
    at = AppTest.from_string(HARNESS_PS); at.run()
    assert not at.exception
    labels = [c.label for c in at.checkbox]
    assert not any("painted mini" in (l or "").lower() for l in labels)


def test_ps_mode_renders_plan_without_error():
    at = AppTest.from_string(HARNESS_PS); at.run()
    assert not at.exception
    # Verify the plan actually rendered: at least one image should appear (combined preview)
    assert len(at.image) > 0


def test_photo_mode_still_shows_coloured_toggle():
    at = AppTest.from_string(HARNESS_PHOTO); at.run()
    assert not at.exception
    labels = [c.label for c in at.checkbox]
    assert any("painted mini" in (l or "").lower() for l in labels)
