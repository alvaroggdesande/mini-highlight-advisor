# ui/state.py
"""The two order-sensitive session-state choreography blocks, centralized.

These are the highest-risk pieces of the editor: getting the load/rehydrate
timing wrong silently corrupts a region's palette. Keep them here, driven by
ui.keys, so the whole 'session-state dance' lives in one place.
"""
import streamlit as st

from mini_highlight_advisor.catalog import find_by_code
from ui import context, keys


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
