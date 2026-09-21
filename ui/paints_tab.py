"""The '🎨 Paints' tab: owned-paint inventory."""
import streamlit as st

from mini_highlight_advisor import collection
from mini_highlight_advisor.catalog import find_by_code
from i18n import t
from ui import context, helpers, keys

_COLL_IMPORT_NONCE = "_coll_import_nonce"


def render() -> tuple[list[str], list]:
    st.markdown(t("paints.heading"))
    owned_codes = collection.load(catalog=context.CATALOG)
    picked = st.multiselect(
        t("paints.multiselect_label"), context.CATALOG_CODES,
        default=sorted(owned_codes & set(context.CATALOG_CODES)),
        format_func=lambda c: context.CODE_LABEL.get(c, c),
        key=keys.OWNED,
    )
    if set(picked) != owned_codes:
        collection.save(set(picked))
    owned_paints = [p for c in picked if (p := find_by_code(context.CATALOG, c)) is not None]

    st.markdown(t("paints.owned_heading"))
    if not owned_paints:
        st.caption(t("paints.no_paints_caption"))
    for p in owned_paints:
        rng = p.paint_range or ""
        st.markdown(f"{helpers.swatch(p.hex)}{p.name} · {rng} · {p.code}", unsafe_allow_html=True)

    st.caption(t("paints.catalogue_caption", count=len(context.CATALOG)))
    _render_collection_io(set(picked))
    return picked, owned_paints


def _render_collection_io(owned: set[str]) -> None:
    with st.expander(t("paints.manage_collection_expander")):
        if owned:
            st.download_button(
                t("paints.download_collection_btn"),
                data=collection.export_to_json_bytes(owned),
                file_name="my_paints.json",
                mime="application/json",
                key="_coll_dl_btn",
            )

        nonce = st.session_state.get(_COLL_IMPORT_NONCE, 0)
        uploader_key = f"_coll_import_{nonce}"

        def _on_import():
            uploaded = st.session_state.get(uploader_key)
            if uploaded is None:
                return
            try:
                imported = collection.import_from_json_bytes(
                    uploaded.read(), catalog=context.CATALOG
                )
                collection.save(imported)
                st.session_state[keys.OWNED] = sorted(imported)
                st.session_state[_COLL_IMPORT_NONCE] = nonce + 1
                st.session_state["_coll_import_count"] = len(imported)
            except Exception as exc:
                st.session_state["_coll_import_err"] = str(exc)

        st.file_uploader(
            t("paints.import_collection_label"),
            type=["json"],
            key=uploader_key,
            on_change=_on_import,
        )
        if count := st.session_state.pop("_coll_import_count", None):
            st.toast(t("paints.collection_imported_toast", count=count))
        if err := st.session_state.pop("_coll_import_err", None):
            st.error(t("paints.import_collection_error", err=err))
