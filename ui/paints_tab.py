"""The '🎨 Paints' tab: owned-paint inventory."""
import streamlit as st

from mini_highlight_advisor import collection
from mini_highlight_advisor.catalog import find_by_code
from ui import context, helpers, keys


def render() -> tuple[list[str], list]:
    st.markdown("**My paints** (Vallejo)")
    owned_codes = collection.load(catalog=context.CATALOG)
    picked = st.multiselect(
        "Paints you own", context.CATALOG_CODES,
        default=sorted(owned_codes & set(context.CATALOG_CODES)),
        format_func=lambda c: context.CODE_LABEL.get(c, c),
        key=keys.OWNED,
    )
    if set(picked) != owned_codes:
        collection.save(set(picked))
    owned_paints = [p for c in picked if (p := find_by_code(context.CATALOG, c)) is not None]

    st.markdown("**Owned paints**")
    if not owned_paints:
        st.caption("No paints selected yet — tick the paints you own above.")
    for p in owned_paints:
        rng = p.paint_range or ""
        st.markdown(f"{helpers.swatch(p.hex)}{p.name} · {rng} · {p.code}", unsafe_allow_html=True)

    st.caption(f"Catalogue: {len(context.CATALOG)} paints (Vallejo Model Color + Game Color)")
    return picked, owned_paints
