# ui/state.py
"""The two order-sensitive session-state choreography blocks, centralized.

These are the highest-risk pieces of the editor: getting the load/rehydrate
timing wrong silently corrupts a region's palette. Keep them here, driven by
ui.keys, so the whole 'session-state dance' lives in one place.
"""
import streamlit as st

from mini_highlight_advisor.catalog import find_by_code
from mini_highlight_advisor import projects
from ui import context, keys


def _current_settings() -> projects.ProjectSettings:
    osl: dict | None = None
    if st.session_state.get(keys.OSL_ON) and st.session_state.get(keys.OSL_POINT):
        pt = st.session_state[keys.OSL_POINT]
        osl = {
            "x": float(pt[0]),
            "y": float(pt[1]),
            "height": float(st.session_state.get(keys.OSL_HEIGHT, 40.0)),
            "reach": float(st.session_state.get(keys.OSL_REACH, 60.0)),
            "intensity": float(st.session_state.get(keys.OSL_INTENSITY, 1.0)),
            "layers": int(st.session_state.get(keys.OSL_LAYERS, 3)),
            "glow": str(st.session_state.get(keys.OSL_GLOW, "#ff9628")),
            "hot": str(st.session_state.get(keys.OSL_HOT, "#ffe6be")),
        }
    return projects.ProjectSettings(
        n=st.session_state.get(keys.N, 5),
        edge_hl=st.session_state.get(keys.EDGE_HL, True),
        edge_extreme=st.session_state.get(keys.EDGE_EXTREME, False),
        edge_sens=st.session_state.get(keys.EDGE_SENS, 0.5),
        relief_cap=st.session_state.get(keys.RELIEF_CAP, True),
        per_region_norm=st.session_state.get(keys.PER_REGION_NORM, False),
        osl=osl,
    )


def seed_editor_from_angle(a) -> None:
    st.session_state[keys.BOOK] = a.book
    st.session_state[keys.LOADED_PHOTO] = {"bytes": a.photo_bytes, "suffix": a.photo_suffix}
    st.session_state[keys.N] = a.settings.n
    st.session_state[keys.EDGE_HL] = a.settings.edge_hl
    st.session_state[keys.EDGE_EXTREME] = a.settings.edge_extreme
    st.session_state[keys.EDGE_SENS] = a.settings.edge_sens
    st.session_state[keys.RELIEF_CAP] = a.settings.relief_cap
    st.session_state[keys.PER_REGION_NORM] = a.settings.per_region_norm
    # Restore OSL params if the loaded angle carried them; clear them otherwise
    # so stale glow from a previous angle does not bleed onto one without OSL.
    osl = getattr(a.settings, "osl", None)
    if osl:
        st.session_state[keys.OSL_ON] = True
        if "x" in osl and "y" in osl:
            st.session_state[keys.OSL_POINT] = (osl["x"], osl["y"])
        if "glow" in osl:
            st.session_state[keys.OSL_GLOW] = osl["glow"]
        if "hot" in osl:
            st.session_state[keys.OSL_HOT] = osl["hot"]
        if "height" in osl:
            st.session_state[keys.OSL_HEIGHT] = osl["height"]
        if "reach" in osl:
            st.session_state[keys.OSL_REACH] = osl["reach"]
        if "intensity" in osl:
            st.session_state[keys.OSL_INTENSITY] = osl["intensity"]
        if "layers" in osl:
            st.session_state[keys.OSL_LAYERS] = osl["layers"]
    else:
        # Angle has no OSL — reset to off so no stale glow leaks across angles.
        st.session_state[keys.OSL_ON] = False
        st.session_state.pop(keys.OSL_POINT, None)
    st.session_state.pop(keys.LOADED_G, None)
    st.session_state.pop(keys.REGION_RADIO, None)
    for k in [k for k in list(st.session_state) if k.startswith(keys.RENAME_PREFIX)]:
        st.session_state.pop(k, None)


def flush_editor_into_angle(a):
    return projects.AngleData(label=a.label, photo_bytes=a.photo_bytes,
                              photo_suffix=a.photo_suffix, book=st.session_state[keys.BOOK],
                              settings=_current_settings())


def set_active_angle(idx: int) -> None:
    """Set the active-angle index and reset the angle-bar radio so it re-seeds
    from index= on the next render (avoids the stale-selected-value bounce)."""
    st.session_state[keys.ACTIVE_ANGLE] = idx
    st.session_state.pop(keys.ANGLE_SELECT, None)


def load_angle_into_editor(idx: int) -> None:
    angles = st.session_state[keys.ANGLES]
    active = st.session_state.get(keys.ACTIVE_ANGLE, 0)
    if idx == active:
        return
    angles[active] = flush_editor_into_angle(angles[active])
    seed_editor_from_angle(angles[idx])
    set_active_angle(idx)
    st.rerun()


def load_region_into_widgets(book, sel) -> None:
    # On selection change, load that region's palette/coverage into widget keys.
    if st.session_state.get(keys.LOADED_G) != sel:
        pal = book.palette_at(sel)
        cov = book.coverage_at(sel)
        st.session_state[keys.N] = len(pal)
        for i, p in enumerate(pal):
            match = find_by_code(context.CATALOG, p.code) if p.code else None
            st.session_state[keys.slot_code(i)] = p.code if match else context.CUSTOM
            st.session_state[keys.slot_hex(i)] = p.hex
        for i in range(len(cov) - 1):
            st.session_state[keys.cov_pct(i)] = round(cov[i] * 100, 1)
        st.session_state[keys.COV_N] = len(cov)
        st.session_state[keys.LOADED_G] = sel
        book.selected = sel
        st.rerun()


def rehydrate_editor_widgets(book, sel) -> None:
    # Restore only the *missing* editor keys from the selected region after a
    # rerun that GC'd them; live user edits (present keys) are untouched.
    _pal = book.palette_at(sel)
    _cov = book.coverage_at(sel)
    st.session_state.setdefault(keys.N, len(_pal))
    for i, p in enumerate(_pal):
        _has_code = bool(p.code) and find_by_code(context.CATALOG, p.code) is not None
        st.session_state.setdefault(keys.slot_code(i), p.code if _has_code else context.CUSTOM)
        st.session_state.setdefault(keys.slot_hex(i), p.hex)
    for i in range(len(_cov) - 1):
        st.session_state.setdefault(keys.cov_pct(i), round(_cov[i] * 100, 1))
    st.session_state.setdefault(keys.COV_N, len(_cov))
