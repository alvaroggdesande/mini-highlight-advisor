# ui/schemes_panel.py
"""🎨 Schemes panel — save the current colours as a named scheme and swap
between saved schemes to compare highlight placement. Streamlit glue only;
all scheme logic lives in mini_highlight_advisor.schemes."""
import streamlit as st

from mini_highlight_advisor import schemes as sch
from ui import keys


def _active_book():
    # PS mode keeps its own book; prefer it when present, else the photo book.
    # Panel only renders in photo mode (app.py's PS branch calls st.stop() first).
    return st.session_state.get(keys.PS_BOOK) or st.session_state.get(keys.BOOK)


def _reseed_editor_widgets() -> None:
    # After a swap the book palettes changed; drop the selected region's widget
    # keys so the editor re-seeds from the book on the next run.
    st.session_state.pop(keys.LOADED_G, None)
    st.session_state.pop(keys.COV_N, None)
    for k in [k for k in list(st.session_state)
              if k.startswith("slot_code_") or k.startswith("slot_hex_")
              or k.startswith("slot_hexinput_") or k.startswith("cov_pct_")]:
        st.session_state.pop(k, None)


def render() -> None:
    book = _active_book()
    if book is None:
        return
    stored = st.session_state.setdefault(keys.SCHEMES, [])
    with st.expander("🎨 Schemes — save & swap colour setups", expanded=False):
        name = st.text_input("Scheme name", key="scheme_save_name")
        if st.button("＋ Save current as scheme", type="primary", key="scheme_save_btn"):
            clean = name.strip()
            if not clean:
                st.warning("Give the scheme a name.")
            else:
                snap = sch.snapshot(book, clean)
                existing = next((s for s in stored if s.name == clean), None)
                if existing:
                    stored[stored.index(existing)] = snap
                    st.toast(f'Updated scheme "{clean}".')
                else:
                    stored.append(snap)
                    st.toast(f'Saved scheme "{clean}".')
                st.rerun()

        if not stored:
            st.caption("No schemes yet. Set your colours, then save one above.")
            return

        names = [s.name for s in stored]
        pick = st.radio("Saved schemes", names, key="scheme_pick")
        chosen = stored[names.index(pick)]

        c_apply, c_del = st.columns(2)
        if c_apply.button("Apply", type="primary", key="scheme_apply_btn"):
            report = sch.apply(chosen, book)
            _reseed_editor_widgets()
            if report.skipped_regions:
                st.session_state["_scheme_note"] = (
                    f"{len(report.updated)} region(s) updated — no saved colour "
                    f"for: {', '.join(report.skipped_regions)}")
            st.rerun()
        if c_del.button("Delete", key="scheme_delete_btn"):
            stored.remove(chosen)
            st.session_state.pop("scheme_pick", None)
            st.rerun()

        new_name = st.text_input("Rename selected", value=pick, key="scheme_rename")
        if st.button("Rename", key="scheme_rename_btn"):
            clean = new_name.strip()
            if not clean or clean == pick:
                pass
            elif any(s.name == clean for s in stored if s is not chosen):
                st.warning(f'A scheme named "{clean}" already exists.')
            else:
                chosen.name = clean
                st.session_state.pop("scheme_pick", None)
                st.rerun()

        note = st.session_state.pop("_scheme_note", None)
        if note:
            st.info(note)
