"""AppTest coverage for PS mode with and without albedo.png in the imported bundle."""
import numpy as np
from pathlib import Path
from PIL import Image
from streamlit.testing.v1 import AppTest
from ui import keys

FIX = Path("tests/fixtures/ps")

# Harness with albedo: pre-seeds NORMALS + PS_MASK + PS_ALBEDO (solid mid-grey),
# then drives ps_mode.render(). The albedo being non-None means relight() will
# return a coloured base — the preview must still render without error.
HARNESS_WITH_ALBEDO = """
import numpy as np
from pathlib import Path
from PIL import Image
import streamlit as st
from mini_highlight_advisor import relight
from ui import ps_mode, keys

FIX = Path("tests/fixtures/ps")
if keys.NORMALS not in st.session_state:
    normals = relight.load_normals(str(FIX / "synth_normal.png"))
    mask = np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127
    h, w = mask.shape
    st.session_state[keys.NORMALS] = normals
    st.session_state[keys.PS_MASK] = mask
    st.session_state[keys.PS_ALBEDO] = np.ones((h, w, 3), np.float32) * 0.5

ps_mode.render(picked=[], owned_paints=[])
st.write("done")
"""

# Harness without albedo: pre-seeds NORMALS + PS_MASK only (PS_ALBEDO absent).
# Must fall back to grey display — same behaviour as before this feature.
HARNESS_NO_ALBEDO = """
import numpy as np
from pathlib import Path
from PIL import Image
import streamlit as st
from mini_highlight_advisor import relight
from ui import ps_mode, keys

FIX = Path("tests/fixtures/ps")
if keys.NORMALS not in st.session_state:
    st.session_state[keys.NORMALS] = relight.load_normals(str(FIX / "synth_normal.png"))
    st.session_state[keys.PS_MASK] = (
        np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127)

ps_mode.render(picked=[], owned_paints=[])
st.write("done")
"""


def test_ps_mode_with_albedo_renders_without_error():
    at = AppTest.from_string(HARNESS_WITH_ALBEDO); at.run()
    assert not at.exception
    assert at.session_state[keys.PS_ALBEDO] is not None


def test_ps_mode_without_albedo_renders_without_error():
    # Regression: existing grey-base path must still work when PS_ALBEDO is absent.
    at = AppTest.from_string(HARNESS_NO_ALBEDO); at.run()
    assert not at.exception


def test_ps_mode_without_albedo_leaves_albedo_key_none():
    at = AppTest.from_string(HARNESS_NO_ALBEDO); at.run()
    assert not at.exception
    # PS_ALBEDO is absent from old sessions — session_state.get() returns None,
    # which is correct backwards-compat behaviour (grey display base, no error).
    assert keys.PS_ALBEDO not in at.session_state
