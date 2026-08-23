"""🖼️ All-angles gallery — a read-only grid of every angle's combined painted
preview, so you can see the same paints across every face at once.

Streamlit glue on top of the same analyze path the editor uses. Per-angle
previews are memoized (keyed by `angle_signature`) so the gallery stays cheap
even though st.tabs runs every tab body on every rerun.
"""
import os
import tempfile

import numpy as np
import streamlit as st

from mini_highlight_advisor.masking import load_image
from mini_highlight_advisor.pipeline import analyze_regions

_PER_ROW = 3


def angle_signature(angle) -> tuple:
    """A hashable identity that changes iff the painted preview would change
    (photo, edge/relief/norm settings, palette hexes, coverage, region masks)."""
    s = angle.settings
    wp, wcov, drawn = angle.book.analyze_args()
    regions = tuple(
        (tuple(p.hex for p in r.palette), tuple(r.coverage),
         r.mask.shape, np.asarray(r.mask, dtype=bool).tobytes())
        for r in drawn
    )
    return (
        angle.photo_bytes, angle.photo_suffix,
        (s.n, s.edge_hl, s.edge_extreme, s.edge_sens, s.relief_cap, s.per_region_norm),
        tuple(p.hex for p in wp), tuple(wcov),
        regions,
    )


def _decode(photo_bytes: bytes, suffix: str):
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(photo_bytes)
        path = tmp.name
    try:
        return load_image(path)
    finally:
        os.unlink(path)


def angle_preview(angle) -> np.ndarray:
    """Decode the angle's photo and return its combined painted preview (uint8
    RGB, same H×W as the source)."""
    rgb, alpha = _decode(angle.photo_bytes, angle.photo_suffix)
    wp, wcov, drawn = angle.book.analyze_args()
    s = angle.settings
    res = analyze_regions(
        rgb, alpha, wp, wcov, drawn,
        edges=s.edge_hl, extreme_edge=s.edge_extreme, edge_sensitivity=s.edge_sens,
        relief_cap=s.relief_cap, per_region_norm=s.per_region_norm,
    )
    return res.combined_rgb


def _cached_preview(angle) -> np.ndarray:
    """Memoize per-angle previews in session so the always-running tab body only
    recomputes an angle when that angle's inputs actually change."""
    cache = st.session_state.setdefault("_gallery_cache", {})
    sig = angle_signature(angle)
    if sig not in cache:
        cache[sig] = angle_preview(angle)
    return cache[sig]


def render(angles, active_idx: int) -> None:
    """Read-only grid of every angle's combined painted preview. The active
    angle is marked; editing happens back in the 🖌️ Miniature tab."""
    if not angles:
        st.info("Add angles in the 🖌️ Miniature tab to see them together here.")
        return

    st.subheader("All angles")
    st.caption("Same paints, every face. Switch to the 🖌️ Miniature tab to edit "
               "the active angle.")

    for start in range(0, len(angles), _PER_ROW):
        cols = st.columns(_PER_ROW)
        for j, angle in enumerate(angles[start:start + _PER_ROW]):
            i = start + j
            with cols[j]:
                try:
                    st.image(_cached_preview(angle), caption=angle.label,
                             use_container_width=True)
                except Exception:  # one bad angle must not blank the whole grid
                    st.warning(f"“{angle.label}” — couldn't render this photo.")
                if i == active_idx:
                    st.caption("Active — open the 🖌️ Miniature tab to edit.")
