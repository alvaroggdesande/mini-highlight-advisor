"""🧭 Angle bar — switch/add/rename/remove the angles of the current mini.

Streamlit glue only; angle state lives in st.session_state[keys.ANGLES] as a
list of projects.AngleData, with keys.ACTIVE_ANGLE the active index.
"""
import os

import streamlit as st

from mini_highlight_advisor import projects
from mini_highlight_advisor.region_state import new_book
from ui import keys, state


def _clear_angle_label_keys() -> None:
    """Pop all angle_label_* widget-state keys to prevent stale text leaking
    across index reuse (the same positional-key bug the repo already fixed for
    region renames via RENAME_PREFIX)."""
    for k in [k for k in list(st.session_state) if k.startswith(keys.ANGLE_LABEL_PREFIX)]:
        st.session_state.pop(k, None)


def render() -> int:
    angles = st.session_state[keys.ANGLES]
    active = st.session_state.get(keys.ACTIVE_ANGLE, 0)

    st.markdown("**Angles**")
    labels = [a.label for a in angles]
    picked = st.radio("Active angle", list(range(len(angles))),
                      index=active, format_func=lambda i: labels[i],
                      horizontal=True, key=keys.ANGLE_SELECT)
    if picked != active:
        state.load_angle_into_editor(picked)   # flush + seed + rerun

    c_rename, c_remove = st.columns([3, 1])
    new_label = c_rename.text_input("Rename angle", value=labels[active],
                                    key=keys.angle_label(active))
    if new_label.strip() and new_label != labels[active]:
        angles[active] = projects.AngleData(
            label=new_label.strip(), photo_bytes=angles[active].photo_bytes,
            photo_suffix=angles[active].photo_suffix, book=angles[active].book,
            settings=angles[active].settings)
        st.rerun()

    if c_remove.button("🗑️ Remove", disabled=len(angles) == 1):
        new_active = projects.next_active_index(active, active, len(angles))
        angles.pop(active)
        state.set_active_angle(new_active)
        _clear_angle_label_keys()
        state.seed_editor_from_angle(angles[new_active])
        st.rerun()

    with st.expander("➕ Add another angle", expanded=False):
        up = st.file_uploader("New angle photo", type=["png", "jpg", "jpeg"],
                              key="add_angle_uploader")
        if up is not None:
            sig = (up.name, up.size)
            if st.session_state.get("_add_angle_sig") != sig:
                st.session_state["_add_angle_sig"] = sig
                # persist edits to the current angle before switching to the new one
                angles[active] = state.flush_editor_into_angle(angles[active])
                a = projects.AngleData(label=f"angle {len(angles) + 1}",
                                       photo_bytes=up.getvalue(),
                                       photo_suffix=os.path.splitext(up.name)[1],
                                       book=new_book(5), settings=angles[active].settings)
                angles.append(a)
                state.set_active_angle(len(angles) - 1)
                _clear_angle_label_keys()
                state.seed_editor_from_angle(a)
                st.rerun()
        else:
            st.session_state.pop("_add_angle_sig", None)

    return st.session_state[keys.ACTIVE_ANGLE]
