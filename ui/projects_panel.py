"""📁 Projects panel — download/upload JSON project files.

No disk writes; works on Streamlit Cloud (ephemeral FS) and locally alike.
All persistence lives in mini_highlight_advisor.projects (project_to/from_json_bytes).
"""
import json

import streamlit as st

from mini_highlight_advisor import projects
from ui import keys, state


def _load_from_project(lp: projects.LoadedProject, name: str) -> None:
    st.session_state[keys.ANGLES] = list(lp.angles)
    state.set_active_angle(lp.active_angle)
    st.session_state[keys.OWNED] = list(lp.paints_pool)
    st.session_state[keys.LOADED_NAME] = name
    state.seed_editor_from_angle(lp.angles[lp.active_angle])
    st.session_state[keys.SCHEMES] = list(lp.schemes)


def render_library() -> None:
    """Upload a previously downloaded project JSON to restore it."""
    with st.expander("📂 Load a saved project", expanded=False):
        nonce = st.session_state.get(keys.UPLOAD_PROJECT_NONCE, 0)
        uploaded = st.file_uploader(
            "Upload project file (.json)",
            type=["json"],
            key=f"{keys.UPLOAD_PROJECT}_{nonce}",
        )
        if uploaded is not None:
            try:
                data = uploaded.read()
                name = json.loads(data).get("name", "Untitled")
                lp = projects.project_from_json_bytes(data)
            except Exception as e:
                st.error(f"Could not load project: {e}")
                return
            _load_from_project(lp, name)
            st.session_state[keys.UPLOAD_PROJECT_NONCE] = nonce + 1
            st.toast(f'Project "{name}" loaded.')
            st.rerun()


def render_save() -> None:
    """Serialize the current project and offer a download button."""
    with st.expander("💾 Download project as JSON", expanded=False):
        default = st.session_state.get(keys.LOADED_NAME, "Untitled")
        name = st.text_input("Project name", value=default, key=keys.SAVE_PROJECT_NAME)
        angles = st.session_state.get(keys.ANGLES, [])
        if not angles:
            st.caption("No mini loaded yet.")
            return
        active = st.session_state.get(keys.ACTIVE_ANGLE, 0)
        flushed = list(angles)
        flushed[active] = state.flush_editor_into_angle(flushed[active])
        pool = list(st.session_state.get(keys.OWNED, []))
        try:
            data = projects.project_to_json_bytes(
                name, pool, active, flushed,
                schemes=st.session_state.get(keys.SCHEMES, []),
            )
            slug = projects.slugify(name)
        except ValueError as e:
            st.error(str(e))
            return
        st.download_button(
            label="⬇ Download project JSON",
            data=data,
            file_name=f"{slug}.json",
            mime="application/json",
        )
