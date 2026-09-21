"""📁 Projects panel — download/upload JSON project files.

No disk writes; works on Streamlit Cloud (ephemeral FS) and locally alike.
All persistence lives in mini_highlight_advisor.projects (project_to/from_json_bytes).
"""
import json

import streamlit as st

from mini_highlight_advisor import projects
from ui import keys, state

_DL_DATA = "_dl_data"
_DL_SLUG = "_dl_slug"
_UPLOAD_ERR = "_upload_error"


def render_library() -> None:
    """Upload a previously downloaded project JSON to restore it."""
    with st.expander("📂 Load a saved project", expanded=False):
        nonce = st.session_state.get(keys.UPLOAD_PROJECT_NONCE, 0)
        uploader_key = f"{keys.UPLOAD_PROJECT}_{nonce}"

        def _on_upload():
            # on_change runs before the next render, so session_state writes are safe.
            uploaded = st.session_state.get(uploader_key)
            if uploaded is None:
                return
            try:
                data = uploaded.read()
                name = json.loads(data).get("name", "Untitled")
                lp = projects.project_from_json_bytes(data)
            except Exception as e:
                st.session_state[_UPLOAD_ERR] = str(e)
                return
            st.session_state[keys.ANGLES] = list(lp.angles)
            state.set_active_angle(lp.active_angle)
            st.session_state[keys.OWNED] = list(lp.paints_pool)
            st.session_state[keys.LOADED_NAME] = name
            state.seed_editor_from_angle(lp.angles[lp.active_angle])
            st.session_state[keys.SCHEMES] = list(lp.schemes)
            st.session_state[keys.UPLOAD_PROJECT_NONCE] = nonce + 1

        st.file_uploader(
            "Upload project file (.json)",
            type=["json"],
            key=uploader_key,
            on_change=_on_upload,
        )

        if err := st.session_state.pop(_UPLOAD_ERR, None):
            st.error(f"Could not load project: {err}")


def render_save() -> None:
    """Serialize the current project and offer a download button.

    Two-step: click Prepare (commits the typed name, encodes JSON) then Download.
    Avoids the Streamlit gotcha where clicking a download button before pressing
    Enter in the text field sends the stale pre-edit filename.
    """
    with st.expander("💾 Download project as JSON", expanded=False):
        default = st.session_state.get(keys.LOADED_NAME, "Untitled")
        name = st.text_input("Project name", value=default, key=keys.SAVE_PROJECT_NAME)
        angles = st.session_state.get(keys.ANGLES, [])
        if not angles:
            st.caption("No mini loaded yet.")
            return

        if st.button("Prepare download", type="primary"):
            active = st.session_state.get(keys.ACTIVE_ANGLE, 0)
            flushed = list(angles)
            flushed[active] = state.flush_editor_into_angle(flushed[active])
            pool = list(st.session_state.get(keys.OWNED, []))
            try:
                data = projects.project_to_json_bytes(
                    name, pool, active, flushed,
                    schemes=st.session_state.get(keys.SCHEMES, []),
                )
                st.session_state[_DL_DATA] = data
                st.session_state[_DL_SLUG] = projects.slugify(name)
            except ValueError as e:
                st.error(str(e))

        if st.session_state.get(_DL_DATA):
            slug = st.session_state[_DL_SLUG]
            st.download_button(
                label=f"⬇ Download {slug}.json",
                data=st.session_state[_DL_DATA],
                file_name=f"{slug}.json",
                mime="application/json",
                key="_dl_btn",
            )
