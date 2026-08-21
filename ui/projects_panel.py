"""📁 Projects panel — save the current mini and reload/delete saved ones.

Streamlit glue only; all persistence lives in mini_highlight_advisor.projects.
"""
import streamlit as st

from mini_highlight_advisor import projects
from mini_highlight_advisor.projects import ProjectSettings
from ui import keys


def _current_settings() -> ProjectSettings:
    return ProjectSettings(
        n=st.session_state.get(keys.N, 5),
        edge_hl=st.session_state.get(keys.EDGE_HL, True),
        edge_extreme=st.session_state.get(keys.EDGE_EXTREME, False),
        edge_sens=st.session_state.get(keys.EDGE_SENS, 0.5),
        relief_cap=st.session_state.get(keys.RELIEF_CAP, True),
        per_region_norm=st.session_state.get(keys.PER_REGION_NORM, False),
    )


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
            st.session_state[keys.LOADED_PHOTO] = {"bytes": lp.photo_bytes,
                                                   "suffix": lp.photo_suffix}
            st.session_state[keys.LOADED_NAME] = labels[slug]
            st.session_state[keys.BOOK] = lp.book
            st.session_state[keys.N] = lp.settings.n
            st.session_state[keys.EDGE_HL] = lp.settings.edge_hl
            st.session_state[keys.EDGE_EXTREME] = lp.settings.edge_extreme
            st.session_state[keys.EDGE_SENS] = lp.settings.edge_sens
            st.session_state[keys.RELIEF_CAP] = lp.settings.relief_cap
            st.session_state[keys.PER_REGION_NORM] = lp.settings.per_region_norm
            st.session_state.pop(keys.LOADED_G, None)
            for k in [k for k in list(st.session_state) if k.startswith(keys.RENAME_PREFIX)]:
                st.session_state.pop(k, None)
            st.rerun()
        confirm_del = st.checkbox("Confirm delete", key=f"confirm_del_{slug}")
        if c_del.button("Delete", disabled=not confirm_del):
            projects.delete_project(slug)
            st.session_state.pop(f"confirm_del_{slug}", None)
            st.rerun()


def render_save(photo_bytes: bytes, photo_suffix: str, book) -> None:
    """Save the current mini. Render this AFTER the book/settings exist this run."""
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
            try:
                projects.save_project(name, photo_bytes, photo_suffix, book,
                                      _current_settings())
                st.session_state[keys.LOADED_NAME] = name
                st.toast(f"Saved \"{name}\".")
            except ValueError as e:
                st.error(str(e))
