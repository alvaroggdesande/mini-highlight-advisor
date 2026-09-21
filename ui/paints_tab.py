"""The '🎨 Paints' tab: owned-paint inventory."""
import streamlit as st

from mini_highlight_advisor import collection
from mini_highlight_advisor.catalog import find_by_code
from i18n import t
from ui import context, helpers, keys


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
    return picked, owned_paints
