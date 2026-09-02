"""AppTest coverage for scheme-preview-on-mini feature.

Tests:
  1. results.render() caches LAST_MULTI + LAST_RGB after each run.
  2. colour_panel renders without error when the cache is warm.
  3. colour_panel renders without error when the cache is cold (no crash).
"""
import numpy as np
from types import SimpleNamespace
from streamlit.testing.v1 import AppTest
from ui import keys

# -- helpers ------------------------------------------------------------------

_PLAN_SETUP = """
import numpy as np
from types import SimpleNamespace

h, w = 10, 10
rgb = np.full((h, w, 3), 128, np.uint8)
mask = np.ones((h, w), bool)
bands = np.zeros((h, w), np.int32)
plans = [SimpleNamespace(
    name="Whole mini",
    sub_mask=mask,
    bands=bands,
    colors=[np.array([10.0, 10.0, 10.0]), np.array([200.0, 200.0, 200.0])],
    edge_overlays=None,
    capped=False,
    flat_albedo=False,
    requested_bands=2,
    roles=["Shadow", "Highlight"],
    names=["Paint A", "Paint B"],
    coverage=[70.0, 30.0],
    steps=[],
)]
multi = SimpleNamespace(mask=mask, light=np.zeros((h, w)), plans=plans,
                        combined_rgb=rgb)
"""

# -- results caching harness --------------------------------------------------

HARNESS_RESULTS = _PLAN_SETUP + """
import streamlit as st
from pathlib import Path
from PIL import Image
from mini_highlight_advisor import relight
from mini_highlight_advisor.masking import compute_mask
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

FIX = Path("tests/fixtures/ps")
normals = relight.load_normals(str(FIX / "synth_normal.png"))
mask_arr = np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127
lf, relit = relight.relight(normals, mask_arr, relight.light_dir(225, 45))
mask_u8 = (mask_arr * 255).astype(np.uint8)
book = new_book(2)
st.session_state[keys.BOOK] = book
wp, wcov, drawn = book.analyze_args()
results.render(relit, mask_u8, book, wp, [], [], None, light_field=lf)
st.write("done")
"""

# -- colour panel harness (warm cache) ----------------------------------------

HARNESS_EDITOR_WARM = _PLAN_SETUP + """
import streamlit as st
from mini_highlight_advisor.region_state import new_book
from ui import colour_panel, keys

st.session_state[keys.LAST_MULTI] = multi
st.session_state[keys.LAST_RGB] = rgb
book = new_book(2)
st.session_state[keys.BOOK] = book
colour_panel.render(book, 0, [], [])
"""

# -- colour panel harness (cold cache — no LAST_MULTI) ------------------------

HARNESS_EDITOR_COLD = """
import streamlit as st
from mini_highlight_advisor.region_state import new_book
from ui import colour_panel, keys

book = new_book(2)
st.session_state[keys.BOOK] = book
colour_panel.render(book, 0, [], [])
"""


# -- tests --------------------------------------------------------------------

def test_results_render_caches_last_multi():
    at = AppTest.from_string(HARNESS_RESULTS); at.run()
    assert not at.exception
    assert keys.LAST_MULTI in at.session_state


def test_results_render_caches_last_rgb():
    at = AppTest.from_string(HARNESS_RESULTS); at.run()
    assert not at.exception
    assert keys.LAST_RGB in at.session_state
    assert isinstance(at.session_state[keys.LAST_RGB], np.ndarray)


def test_colour_panel_no_crash_when_cache_warm():
    at = AppTest.from_string(HARNESS_EDITOR_WARM); at.run()
    assert not at.exception


def test_colour_panel_no_crash_when_cache_cold():
    at = AppTest.from_string(HARNESS_EDITOR_COLD); at.run()
    assert not at.exception
