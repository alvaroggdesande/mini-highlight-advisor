# tests/test_ui_nmm.py
from streamlit.testing.v1 import AppTest

# PS mode: has_normals=True so NMM option is available in the technique picker.
HARNESS_PS = """
import streamlit as st
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

book = new_book(5)
st.session_state[keys.BOOK] = book
results.render_technique_controls(book, 0, has_normals=True)
st.write("ok")
"""

# Photo mode: has_normals=False -> NMM controls must be absent.
HARNESS_PHOTO = """
import streamlit as st
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

book = new_book(5)
st.session_state[keys.BOOK] = book
results.render_technique_controls(book, 0, has_normals=False)
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
    # Images are now rendered by render_steps(), not render()


def test_photo_mode_shows_technique_but_hides_horizon():
    # Technique picker is always visible; NMM option and horizon slider are PS-only.
    at = AppTest.from_string(HARNESS_PHOTO); at.run()
    assert not at.exception
    labels = [(s.label or "").lower() for s in at.selectbox]
    assert any("technique" in l for l in labels)
    # NMM should not be an option in photo mode.
    tech = next(s for s in at.selectbox if "technique" in (s.label or "").lower())
    assert "NMM" not in tech.options
    # Horizon slider and NMM env controls must not appear in photo mode.
    slider_labels = [(s.label or "").lower() for s in at.slider]
    assert not any("horizon" in l for l in slider_labels)
    assert not any("light direction" in l for l in slider_labels)
    assert not any("bounce" in l for l in slider_labels)
    assert not any("hotspot" in l for l in slider_labels)


def test_ps_mode_shows_metal_environment_panel_and_preview():
    # Metal env panel only appears after NMM is selected.
    at = AppTest.from_string(HARNESS_PS); at.run()
    tech = next(s for s in at.selectbox if "technique" in (s.label or "").lower())
    tech.set_value("NMM").run()
    assert not at.exception
    select_labels = [(s.label or "").lower() for s in at.selectbox]
    assert any("preset" in l or "metal environment" in l for l in select_labels)
    slider_labels = [(s.label or "").lower() for s in at.slider]
    assert any("light direction" in l for l in slider_labels)


def test_selecting_preset_and_moving_knobs_replans_without_error():
    at = AppTest.from_string(HARNESS_PS); at.run()
    tech = next(s for s in at.selectbox if "technique" in (s.label or "").lower())
    tech.set_value("NMM").run()
    preset = next(s for s in at.selectbox if "preset" in (s.label or "").lower())
    preset.set_value("Gold").run()
    assert not at.exception
    assert len(at.image) > 0  # env-disk preview image
