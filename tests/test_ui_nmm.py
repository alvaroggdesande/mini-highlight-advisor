# tests/test_ui_nmm.py
from streamlit.testing.v1 import AppTest

HARNESS_EDITOR_PS = """
import numpy as np
from pathlib import Path
from PIL import Image
import streamlit as st
from mini_highlight_advisor import relight
from mini_highlight_advisor.region_state import new_book
from ui import editor, keys

FIX = Path("tests/fixtures/ps")
normals = relight.load_normals(str(FIX / "synth_normal.png"))
mask = np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127
lf, relit = relight.relight(normals, mask, relight.light_dir(225, 45))
mask_u8 = (mask * 255).astype(np.uint8)
book = new_book(5)
st.session_state[keys.BOOK] = book
sh = type('S', (), {'mask': mask})()
editor.render_editor(relit, mask_u8, sh, book, [], [],
                     light_field=lf, normal_field=normals)
st.write("ok")
"""

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


def test_ps_mode_shows_material_selector_and_horizon():
    at = AppTest.from_string(HARNESS_PS); at.run()
    assert not at.exception
    labels = [(s.label or "").lower() for s in at.selectbox]
    assert any("material" in l for l in labels)
    slider_labels = [(s.label or "").lower() for s in at.slider]
    assert any("horizon" in l for l in slider_labels)


def test_ps_mode_selecting_nmm_replans_without_error():
    at = AppTest.from_string(HARNESS_PS); at.run()
    mat = next(s for s in at.selectbox if "material" in (s.label or "").lower())
    mat.set_value("NMM").run()
    assert not at.exception
    assert len(at.image) > 0            # combined preview still renders


def test_photo_mode_hides_material_and_horizon():
    at = AppTest.from_string(HARNESS_PHOTO); at.run()
    assert not at.exception
    labels = [(s.label or "").lower() for s in at.selectbox]
    assert not any("material" in l for l in labels)
    # PS-only env controls must also be absent in photo mode.
    assert not any("preset" in l for l in labels)
    slider_labels = [(s.label or "").lower() for s in at.slider]
    assert not any("horizon" in l for l in slider_labels)
    assert not any("light direction" in l for l in slider_labels)
    assert not any("bounce" in l for l in slider_labels)
    assert not any("hotspot" in l for l in slider_labels)


def test_selecting_nmm_swaps_coverage_for_metal_steps():
    at = AppTest.from_string(HARNESS_EDITOR_PS); at.run()
    assert not at.exception
    mat = next(s for s in at.selectbox if "material" in (s.label or "").lower())
    mat.set_value("NMM").run()
    assert not at.exception
    number_labels = [(ni.label or "").lower() for ni in at.number_input]
    assert any("metal steps" in l for l in number_labels)
    # coverage role sliders (e.g. "Shadow"/"Base") are gone for the NMM region
    slider_labels = [(s.label or "").lower() for s in at.slider]
    assert not any(l in ("shadow", "base", "midtone", "highlight") for l in slider_labels)


def test_ps_mode_shows_metal_environment_panel_and_preview():
    at = AppTest.from_string(HARNESS_PS); at.run()
    assert not at.exception
    select_labels = [(s.label or "").lower() for s in at.selectbox]
    assert any("preset" in l or "metal environment" in l for l in select_labels)
    slider_labels = [(s.label or "").lower() for s in at.slider]
    assert any("light direction" in l for l in slider_labels)


def test_selecting_preset_and_moving_knobs_replans_without_error():
    at = AppTest.from_string(HARNESS_PS); at.run()
    preset = next(s for s in at.selectbox if "preset" in (s.label or "").lower())
    preset.set_value("Gold").run()
    assert not at.exception
    assert len(at.image) > 0
