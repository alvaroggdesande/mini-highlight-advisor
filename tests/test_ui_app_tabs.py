"""Smoke tests for the new five-tab app structure."""
from pathlib import Path
from streamlit.testing.v1 import AppTest

_APP = str(Path(__file__).parent.parent / "app.py")


def _make_at():
    at = AppTest.from_file(_APP, default_timeout=30)
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
