"""Smoke tests for the new five-tab app structure."""
import io
import numpy as np
from pathlib import Path
from PIL import Image
from streamlit.testing.v1 import AppTest

_APP = str(Path(__file__).parent.parent / "app.py")


def _make_at():
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    return at


def _png_bytes(h: int = 20, w: int = 20) -> bytes:
    """Return a tiny valid greyscale PNG as bytes."""
    arr = np.full((h, w, 3), 128, dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _make_at_with_photo():
    """Return an AppTest with a synthetic photo pre-seeded in session_state."""
    from mini_highlight_advisor import projects
    from mini_highlight_advisor.region_state import new_book
    from ui import state, keys

    at = AppTest.from_file(_APP, default_timeout=30)
    photo = _png_bytes()
    a = projects.AngleData(
        label="angle 1", photo_bytes=photo, photo_suffix=".png",
        book=new_book(5), settings=state._current_settings())
    at.session_state[keys.ANGLES] = [a]
    at.session_state[keys.ACTIVE_ANGLE] = 0
    at.session_state[keys.BOOK] = a.book
    at.run()
    return at


def test_app_loads_without_error():
    at = _make_at()
    assert not at.exception


def test_five_tabs_present():
    at = _make_at()
    tab_labels = [t.label for t in at.tabs]
    assert "🖌️ Studio" in tab_labels
    assert "🪜 Paint" in tab_labels
    assert "📷 Capture & help" in tab_labels


def test_studio_tab_shows_upload_prompt_before_upload():
    at = _make_at()
    # Before upload, Studio tab shows its upload prompt info box.
    # (st.stop() inside tab_studio prevents later tabs from rendering in this
    # state, so we assert the Studio prompt rather than the Paint placeholder.)
    infos = [i.value for i in at.info]
    assert any("primed miniature" in t for t in infos)


def test_studio_has_sub_tabs():
    at = _make_at_with_photo()
    # All tabs (top-level + sub-tabs) are returned by at.tabs; labels may include emoji.
    all_labels = [t.label for t in at.tabs]
    assert any("Regions" in lbl for lbl in all_labels)
    assert any("Colour" in lbl for lbl in all_labels)
    assert any("Technique" in lbl for lbl in all_labels)
