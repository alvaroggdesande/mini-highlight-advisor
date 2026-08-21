"""Version-compat shims, isolated so they are easy to retire later.

Importing this module (a) monkey-patches streamlit.elements.image.image_to_url
for streamlit-drawable-canvas 0.9.3 against streamlit 1.61.*, then (b) imports
st_canvas, then (c) sets the HF symlink-warning env var. Order matters: the
patch must run before the drawable-canvas import.
"""
import os


def _patch_image_to_url() -> None:
    # streamlit-drawable-canvas 0.9.3 calls the private helper
    # streamlit.elements.image.image_to_url(image, width, ...), which newer
    # Streamlit moved to streamlit.elements.lib.image_utils.image_to_url and
    # changed the 2nd arg from `width: int` to `layout_config` (only `.width`
    # is read). Re-expose an adapter so the component works unmodified. Pinned
    # to streamlit 1.61.* in requirements.txt; revisit on a major upgrade.
    import streamlit.elements.image as _si
    if hasattr(_si, "image_to_url"):
        return
    try:
        from types import SimpleNamespace
        from streamlit.elements.lib import image_utils as _iu

        def image_to_url(image, width, clamp, channels, output_format, image_id):
            return _iu.image_to_url(
                image, SimpleNamespace(width=width), clamp, channels, output_format, image_id
            )

        _si.image_to_url = image_to_url
    except Exception:
        pass  # leave unpatched -> st_canvas import/use degrades, single-palette still works


_patch_image_to_url()

try:
    from streamlit_drawable_canvas import st_canvas
except Exception:  # component missing/incompatible -> region drawing off, single-palette still works
    st_canvas = None

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
