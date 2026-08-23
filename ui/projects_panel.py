"""📁 Projects panel — save the current mini and reload/delete saved ones.

Streamlit glue only; all persistence lives in mini_highlight_advisor.projects.
"""
import streamlit as st

from mini_highlight_advisor import projects
from ui import keys, state


def render_library() -> None:
    """Load / delete existing projects. Render this BEFORE the upload gate."""
    with st.expander("📁 Projects — load a saved mini", expanded=False):
        metas = projects.list_projects()
        if not metas:
            st.caption("No saved projects yet. Save one below after setting up a mini.")
            return
        labels = {m.slug: f"{m.name}" for m in metas}
        slug = st.selectbox("Saved projects", [m.slug for m in metas],
                            format_func=lambda s: labels[s], key=keys.LOAD_SELECT)
        c_load, c_del = st.columns(2)
        if c_load.button("Load", type="primary"):
            lp = projects.load_project(slug)
            st.session_state[keys.ANGLES] = list(lp.angles)
            state.set_active_angle(lp.active_angle)
            st.session_state[keys.OWNED] = list(lp.paints_pool)
            st.session_state[keys.LOADED_NAME] = labels[slug]
            state.seed_editor_from_angle(lp.angles[lp.active_angle])
            st.rerun()
        confirm_del = st.checkbox("Confirm delete", key=f"confirm_del_{slug}")
        if c_del.button("Delete", disabled=not confirm_del):
            projects.delete_project(slug)
            st.session_state.pop(f"confirm_del_{slug}", None)
            st.rerun()


def render_save() -> None:
    """Save the whole mini (all angles + shared paint pool). Render AFTER the editor."""
    with st.expander("💾 Save this mini as a project", expanded=False):
        default = st.session_state.get(keys.LOADED_NAME, "Untitled")
        name = st.text_input("Project name", value=default, key=keys.SAVE_PROJECT_NAME)
        existing = {m.slug for m in projects.list_projects()}
        try:
            will_overwrite = projects.slugify(name) in existing
        except ValueError:
            will_overwrite = False
        if will_overwrite:
            st.warning(f"A project named \"{name}\" exists — saving overwrites it.")
        ok = (not will_overwrite) or st.checkbox("Confirm overwrite", key=f"confirm_ow_{name}")
        if st.button("Save project", type="primary", disabled=not ok):
            angles = st.session_state[keys.ANGLES]
            active = st.session_state.get(keys.ACTIVE_ANGLE, 0)
            # flush live edits of the active angle before serializing
            angles[active] = state.flush_editor_into_angle(angles[active])
            pool = list(st.session_state.get(keys.OWNED, []))
            try:
                projects.save_project(name, pool, active, angles)
                st.session_state[keys.LOADED_NAME] = name
                st.toast(f"Saved \"{name}\".")
            except ValueError as e:
                st.error(str(e))
