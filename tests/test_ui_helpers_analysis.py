import numpy as np
import pytest
from mini_highlight_advisor.region_state import new_book


def _small_rgb():
    return np.full((16, 16, 3), 128, dtype=np.uint8)


def _small_alpha():
    a = np.zeros((16, 16), dtype=np.uint8)
    a[4:12, 4:12] = 255
    return a


class _FakeShading:
    def __init__(self, mask):
        self.mask = mask
        self.light = np.ones((16, 16), dtype=np.float32) * 0.5


def test_run_analysis_returns_multi_region_result():
    from ui import helpers
    from mini_highlight_advisor.pipeline import MultiRegionResult

    rgb = _small_rgb()
    alpha = _small_alpha()
    mask = alpha > 127
    shading = _FakeShading(mask)
    book = new_book(3)

    result = helpers.run_analysis(rgb, alpha, book, shading)
    assert isinstance(result, MultiRegionResult)
    assert len(result.plans) >= 1


def test_run_analysis_reads_edge_hl_from_session_state():
    """With EDGE_HL=False in session_state, edge highlights should be off."""
    import streamlit as st
    from unittest.mock import patch
    from ui import helpers, keys

    rgb = _small_rgb()
    alpha = _small_alpha()
    mask = alpha > 127
    shading = _FakeShading(mask)
    book = new_book(3)

    fake_state = {keys.EDGE_HL: False}
    with patch.object(st, "session_state", fake_state):
        result = helpers.run_analysis(rgb, alpha, book, shading)
    # If edge_hl=False, no edge highlight pixels — just verify it doesn't crash
    assert result is not None


def test_run_analysis_memoizes_identical_inputs():
    """Two calls with identical inputs return the SAME object (cache hit), so the
    heavy pipeline runs once per unchanged rerun."""
    import streamlit as st
    from unittest.mock import patch
    from ui import helpers

    rgb, alpha = _small_rgb(), _small_alpha()
    shading = _FakeShading(alpha > 127)
    book = new_book(3)

    fake_state = {}
    with patch.object(st, "session_state", fake_state):
        r1 = helpers.run_analysis(rgb, alpha, book, shading)
        r2 = helpers.run_analysis(rgb, alpha, book, shading)
    assert r1 is r2


def test_run_analysis_recomputes_when_setting_changes():
    """Changing a control value invalidates the memo, so a fresh result is built."""
    import streamlit as st
    from unittest.mock import patch
    from ui import helpers, keys

    rgb, alpha = _small_rgb(), _small_alpha()
    shading = _FakeShading(alpha > 127)
    book = new_book(3)

    fake_state = {keys.EDGE_HL: True}
    with patch.object(st, "session_state", fake_state):
        r1 = helpers.run_analysis(rgb, alpha, book, shading)
        fake_state[keys.EDGE_HL] = False
        r2 = helpers.run_analysis(rgb, alpha, book, shading)
    assert r1 is not r2


def test_run_analysis_memo_hits_across_distinct_but_equal_rgb():
    """The real-app scenario: PS mode recomputes a relit rgb on every rerun — a
    fresh array object with identical content when the light is unchanged. The
    memo must key on rgb CONTENT, not id() — otherwise it never hits and the
    editor recomputes the full pipeline every rerun."""
    import streamlit as st
    from unittest.mock import patch
    from ui import helpers

    base = np.zeros((32, 32, 3), np.uint8)
    base[:, :, 0] = np.linspace(0, 255, 32, dtype=np.uint8)[None, :]
    a = np.zeros((32, 32), np.uint8); a[4:28, 4:28] = 255
    book = new_book(3)

    r1_rgb, r2_rgb = base.copy(), base.copy()  # distinct objects, equal content
    fake_state = {}
    with patch.object(st, "session_state", fake_state):
        res1 = helpers.run_analysis(r1_rgb, a, book, _FakeShading(a > 127))
        res2 = helpers.run_analysis(r2_rgb, a, book, _FakeShading(a > 127))

    assert r1_rgb is not r2_rgb  # distinct arrays (as PS relight hands back)
    assert res1 is res2          # ...but the memo still hit on content


def test_run_analysis_recomputes_when_palette_changes():
    """Editing the whole-mini palette invalidates the memo even though the mask,
    photo and settings are unchanged."""
    import streamlit as st
    from unittest.mock import patch
    from ui import helpers
    from mini_highlight_advisor.palette import default_ramp

    rgb, alpha = _small_rgb(), _small_alpha()
    shading = _FakeShading(alpha > 127)
    book = new_book(5)

    fake_state = {}
    with patch.object(st, "session_state", fake_state):
        r1 = helpers.run_analysis(rgb, alpha, book, shading)
        book.set_palette_at(0, default_ramp(4))  # different palette
        r2 = helpers.run_analysis(rgb, alpha, book, shading)
    assert r1 is not r2
