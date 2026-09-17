"""🖼️ All-angles gallery — a read-only grid of every angle's combined painted
preview, so you can see the same paints across every face at once.

Streamlit glue on top of the same analyze path the editor uses. Per-angle
previews are memoized (keyed by `angle_signature`) so the gallery stays cheap
even though st.tabs runs every tab body on every rerun.
"""
import weakref

import numpy as np
import streamlit as st

from mini_highlight_advisor.pipeline import analyze_regions
from ui import keys, state, _profile

_PER_ROW = 3

# Content fingerprint per mask array, so angle_signature (which runs for every
# angle on every rerun, because st.tabs bodies all execute each pass) hashes a
# multi-megapixel mask only ONCE per array object instead of on every rerun.
# Region masks are immutable once drawn, so keying the cache by object identity is
# exact; the weakref callback drops the entry the moment a mask is GC'd, so a
# recycled id() can never hand back a stale fingerprint. The VALUE is content-based
# (shape + tobytes hash), so two distinct-but-equal masks still compare equal.
_MASK_FP: dict[int, tuple] = {}
_MASK_KEEP: dict[int, "weakref.ref"] = {}


def _mask_fingerprint(mask) -> tuple:
    k = id(mask)
    fp = _MASK_FP.get(k)
    if fp is not None:
        return fp
    m = np.asarray(mask, dtype=bool)
    fp = (m.shape, hash(m.tobytes()))
    try:
        _MASK_KEEP[k] = weakref.ref(mask, lambda _r, k=k: (
            _MASK_FP.pop(k, None), _MASK_KEEP.pop(k, None)))
    except TypeError:
        return fp  # non-weakreffable: don't cache under a reusable id, recompute
    _MASK_FP[k] = fp
    return fp


def angle_signature(angle) -> tuple:
    """A hashable identity that changes iff the painted preview would change
    (photo, edge/relief/norm settings, palette hexes, coverage, region masks)."""
    s = angle.settings
    wp, wcov, drawn = angle.book.analyze_args()
    regions = tuple(
        (tuple(p.hex for p in r.palette), tuple(r.coverage), _mask_fingerprint(r.mask))
        for r in drawn
    )
    return (
        angle.photo_bytes, angle.photo_suffix,
        (s.n, s.edge_hl, s.edge_extreme, s.edge_sens, s.relief_cap, s.per_region_norm),
        tuple(p.hex for p in wp), tuple(wcov),
        # Whole-mini visibility/material aren't in analyze_args (region 0 has no mask
        # here), so fold them in explicitly or toggling the "Whole mini" region off
        # would leave the cached gallery preview stale.
        angle.book.whole_blank, angle.book.material_at(0),
        regions,
    )


def angle_preview(angle) -> np.ndarray:
    """Decode the angle's photo and return its combined painted preview (uint8
    RGB, same H×W as the source).

    Decode + mask come from the shared `helpers.shading()` cache (cache_resource),
    so the expensive mask computation (GrabCut for no-alpha photos) runs once per
    photo — reused across reruns and shared with the editor for the active angle —
    instead of on every gallery miss.
    """
    from ui import helpers
    rgb, alpha, shading = helpers.shading(angle.photo_bytes, angle.photo_suffix)
    wp, wcov, drawn = angle.book.analyze_args()
    s = angle.settings
    res = analyze_regions(
        rgb, alpha, wp, wcov, drawn,
        edges=s.edge_hl, extreme_edge=s.edge_extreme, edge_sensitivity=s.edge_sens,
        relief_cap=s.relief_cap, per_region_norm=s.per_region_norm,
        whole_material=angle.book.material_at(0), whole_blank=angle.book.whole_blank,
        shading=shading,
    )
    return res.combined_rgb


def _cached_preview(angle) -> np.ndarray:
    """Memoize per-angle previews in session so the always-running tab body only
    recomputes an angle when that angle's inputs actually change."""
    cache = st.session_state.setdefault("_gallery_cache", {})
    with _profile.prof("gallery: angle_signature"):
        sig = angle_signature(angle)
    if sig not in cache:
        _profile.mark(f"gallery: MISS -> analyze angle '{getattr(angle, 'label', '?')}'")
        with _profile.prof("gallery: angle_preview (analyze)"):
            cache[sig] = angle_preview(angle)
    return cache[sig]


def render(angles, active_idx: int) -> None:
    """Read-only grid of every angle's combined painted preview. The active
    angle is marked; editing happens back in the 🖌️ Miniature tab."""
    if not angles:
        st.info("Add angles in the 🖌️ Miniature tab to see them together here.")
        return
    _profile.mark(f"ALL-ANGLES tab: rendering {len(angles)} angle(s)")

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
                if st.button("Edit", key=f"gallery_edit_{i}"):
                    # Must go through the proper switch (flush + seed + pop the
                    # angle-radio key). Setting ACTIVE_ANGLE alone desyncs the
                    # studio angle radio: it keeps its old value and bounces the
                    # active angle straight back on the next rerun.
                    state.load_angle_into_editor(i)
                if i == active_idx:
                    st.caption("Active — open the 🖌️ Miniature tab to edit.")
