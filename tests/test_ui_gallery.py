"""Tests for the combined 'All angles' gallery (ui/gallery_panel)."""
import io

import numpy as np
import pytest
from PIL import Image

from mini_highlight_advisor import projects
from mini_highlight_advisor.region_state import RegionBook
from mini_highlight_advisor.regions import Region
from mini_highlight_advisor.palette import default_ramp, default_coverage

from ui import gallery_panel, keys


def _png_bytes(w=32, h=32) -> bytes:
    """A small RGBA image with a solid alpha square so masking uses the fast
    alpha path (no GrabCut) and there is tonal variation for banding to read."""
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    grad = np.linspace(20, 220, w, dtype=np.uint8)
    rgb[:, :, :] = grad[None, :, None]
    alpha = np.zeros((h, w), dtype=np.uint8)
    alpha[4:h - 4, 4:w - 4] = 255
    im = Image.fromarray(np.dstack([rgb, alpha]), mode="RGBA")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _settings(**kw):
    base = dict(n=5, edge_hl=True, edge_extreme=False, edge_sens=0.5,
                relief_cap=True, per_region_norm=False)
    base.update(kw)
    return projects.ProjectSettings(**base)


def _angle(label="front", photo=None, book=None, settings=None):
    return projects.AngleData(
        label=label,
        photo_bytes=photo if photo is not None else _png_bytes(),
        photo_suffix=".png",
        book=book if book is not None else RegionBook(default_ramp(5), default_coverage(5)),
        settings=settings or _settings(),
    )


# --- angle_signature: stable identity that changes iff the preview would ---

def test_signature_stable_for_equal_angles():
    photo = _png_bytes()
    assert gallery_panel.angle_signature(_angle(photo=photo)) == \
        gallery_panel.angle_signature(_angle(photo=photo))


def test_signature_changes_when_palette_changes():
    photo = _png_bytes()
    a = _angle(photo=photo)
    book2 = RegionBook(default_ramp(5), default_coverage(5))
    book2.set_palette_at(0, default_ramp(4))  # different palette
    b = _angle(photo=photo, book=book2)
    assert gallery_panel.angle_signature(a) != gallery_panel.angle_signature(b)


def test_signature_changes_when_settings_change():
    photo = _png_bytes()
    a = _angle(photo=photo, settings=_settings(edge_hl=True))
    b = _angle(photo=photo, settings=_settings(edge_hl=False))
    assert gallery_panel.angle_signature(a) != gallery_panel.angle_signature(b)


def test_signature_changes_when_region_mask_changes():
    photo = _png_bytes()
    m1 = np.zeros((32, 32), dtype=bool); m1[6:10, 6:10] = True
    m2 = np.zeros((32, 32), dtype=bool); m2[20:24, 20:24] = True
    b1 = RegionBook(default_ramp(5), default_coverage(5),
                    drawn=[Region("r", m1, default_ramp(4), default_coverage(4))])
    b2 = RegionBook(default_ramp(5), default_coverage(5),
                    drawn=[Region("r", m2, default_ramp(4), default_coverage(4))])
    assert gallery_panel.angle_signature(_angle(photo=photo, book=b1)) != \
        gallery_panel.angle_signature(_angle(photo=photo, book=b2))


def test_signature_changes_when_whole_mini_blanked():
    """Toggling the 'Whole mini' region off must invalidate the gallery cache, or
    the all-angles preview stays stale (region 0 has no mask in analyze_args)."""
    photo = _png_bytes()
    a = _angle(photo=photo)
    book2 = RegionBook(default_ramp(5), default_coverage(5))
    book2.whole_blank = True
    b = _angle(photo=photo, book=book2)
    assert gallery_panel.angle_signature(a) != gallery_panel.angle_signature(b)


def test_signature_is_hashable():
    hash(gallery_panel.angle_signature(_angle()))


# --- angle_preview: decode + analyze -> combined RGB image ---

def test_preview_returns_rgb_matching_source_size():
    img = gallery_panel.angle_preview(_angle())
    assert isinstance(img, np.ndarray)
    assert img.shape == (32, 32, 3)
    assert img.dtype == np.uint8


# --- render(): the Streamlit gallery grid (driven via AppTest) ---

from streamlit.testing.v1 import AppTest  # noqa: E402

_HARNESS = """
import io
import numpy as np
from PIL import Image
import streamlit as st
from mini_highlight_advisor import projects
from mini_highlight_advisor.region_state import RegionBook
from mini_highlight_advisor.palette import default_ramp, default_coverage
from ui import gallery_panel, keys, state

def _png():
    rgb = np.zeros((32, 32, 3), dtype=np.uint8)
    rgb[:, :, :] = np.linspace(20, 220, 32, dtype=np.uint8)[None, :, None]
    a = np.zeros((32, 32), dtype=np.uint8); a[4:28, 4:28] = 255
    buf = io.BytesIO(); Image.fromarray(np.dstack([rgb, a]), "RGBA").save(buf, "PNG")
    return buf.getvalue()

def _angle(label):
    return projects.AngleData(label=label, photo_bytes=_png(), photo_suffix=".png",
        book=RegionBook(default_ramp(5), default_coverage(5)),
        settings=projects.ProjectSettings(5, True, False, 0.5, True, False))

n = int(st.session_state.get("_n_angles", 2))
if keys.ANGLES not in st.session_state:
    st.session_state[keys.ANGLES] = [_angle(f"angle {i+1}") for i in range(n)]
    st.session_state[keys.ACTIVE_ANGLE] = 0
    if n:
        state.seed_editor_from_angle(st.session_state[keys.ANGLES][0])

gallery_panel.render(st.session_state[keys.ANGLES],
                     st.session_state.get(keys.ACTIVE_ANGLE, 0))
"""


def _run(n_angles=2):
    at = AppTest.from_string(_HARNESS)
    at.session_state["_n_angles"] = n_angles
    at.run()
    return at


def test_render_shows_one_preview_image_per_angle():
    at = _run(2)
    assert len(at.get("image")) == 2


def test_render_shows_an_edit_button_per_angle():
    at = _run(2)
    assert at.button(key="gallery_edit_0") is not None
    assert at.button(key="gallery_edit_1") is not None


def test_edit_button_sets_active_angle():
    at = _run(2)
    at.button(key="gallery_edit_1").click()
    at.run()
    assert at.session_state[keys.ACTIVE_ANGLE] == 1


def test_render_with_no_angles_shows_placeholder_not_crash():
    at = _run(0)
    assert not at.exception
    assert len(at.get("image")) == 0
