"""🧭 Angle bar — switch/add/rename/remove the angles of the current mini.

Streamlit glue only; angle state lives in st.session_state[keys.ANGLES] as a
list of projects.AngleData, with keys.ACTIVE_ANGLE the active index.
"""
import os

import streamlit as st

from mini_highlight_advisor import projects
from mini_highlight_advisor.region_state import new_book
from ui import keys, state


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
        st.session_state[keys.ACTIVE_ANGLE] = new_active
        state.seed_editor_from_angle(angles[new_active])
        st.rerun()

    with st.expander("➕ Add another angle", expanded=False):
        up = st.file_uploader("New angle photo", type=["png", "jpg", "jpeg"],
                              key="add_angle_uploader")
        if up is not None:
            # persist edits to the current angle before switching to the new one
            angles[active] = state.flush_editor_into_angle(angles[active])
            a = projects.AngleData(label=f"angle {len(angles) + 1}",
                                   photo_bytes=up.getvalue(),
                                   photo_suffix=os.path.splitext(up.name)[1],
                                   book=new_book(5), settings=angles[active].settings)
            angles.append(a)
            st.session_state[keys.ACTIVE_ANGLE] = len(angles) - 1
            state.seed_editor_from_angle(a)
            st.rerun()

    return st.session_state[keys.ACTIVE_ANGLE]
