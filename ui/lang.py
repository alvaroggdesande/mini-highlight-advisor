import streamlit as st
from i18n import set_lang, available_langs, t

_LANG_LABELS = {
    "en": "🇬🇧 English",
    "es": "🇪🇸 Español",
}


def init_lang() -> None:
    """Call once at app startup, before any other st.* calls."""
    lang = st.query_params.get("lang", "en")
    if lang not in available_langs():
        lang = "en"
    st.session_state["lang"] = lang
    set_lang(lang)


def lang_selector() -> None:
    """Render language selectbox in sidebar. Rewrites URL param and reruns on change."""
    langs = available_langs()
    current = st.session_state.get("lang", "en")
    chosen = st.sidebar.selectbox(
        t("sidebar.language"),
        langs,
        index=langs.index(current) if current in langs else 0,
        format_func=lambda lang: _LANG_LABELS.get(lang, lang),
    )
    if chosen != current:
        st.query_params["lang"] = chosen
        st.rerun()
