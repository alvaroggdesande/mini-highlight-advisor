"""Palette slots + recipe load/save editor panel.

Public API:
    render(book, sel, picked) -> tuple[list[PaintColor], int]
        Renders the recipe loader then the palette slots.
        Returns (palette, n).
    render_save_recipe(palette, n) -> None
        Renders the "Save as recipe" expander.
"""
import streamlit as st
from collections import Counter

from mini_highlight_advisor.palette import DEFAULT_PALETTE, PaintColor, role_names, ramp_hex, valid_hex
from mini_highlight_advisor.color import blend_hex_lab, hue_rotate, ramp_from_midtone
from mini_highlight_advisor.recipes import load_all, to_palette, save_user, Recipe, RecipeStep
from mini_highlight_advisor.catalog import find_by_code, find_by_name
from mini_highlight_advisor import collection
from ui import context, helpers, keys


def _apply_paste_hex(i: int) -> None:
    norm = valid_hex(st.session_state.get(keys.slot_hexinput(i), ""))
    if norm is not None:
        st.session_state[keys.slot_hex(i)] = norm


def _blend_neighbours(i: int, n: int) -> None:
    lo = st.session_state.get(keys.slot_hex(i - 1), ramp_hex(i - 1, n))
    hi = st.session_state.get(keys.slot_hex(i + 1), ramp_hex(i + 1, n))
    st.session_state[keys.slot_hex(i)] = blend_hex_lab(lo, hi)
    st.session_state[keys.slot_code(i)] = context.CUSTOM


def render(book, sel, picked) -> tuple[list[PaintColor], int]:
    """Render the recipe loader then the palette slots. Returns (palette, n)."""
    # --- recipe loader ---
    recipes = load_all()
    recipe_by_name = {r.name: r for r in recipes}
    name_counts = Counter(p.name for p in context.CATALOG)
    choice = st.selectbox("Recipe", ["(none)"] + list(recipe_by_name))
    if st.button("Load") and choice != "(none)":
        pal = to_palette(recipe_by_name[choice])
        st.session_state[keys.N] = max(3, min(5, len(pal)))
        for i, p in enumerate(pal[:st.session_state[keys.N]]):
            match = find_by_name(context.CATALOG, p.name)
            unique = name_counts.get(p.name) == 1
            st.session_state[keys.slot_code(i)] = match.code if (match and unique) else context.CUSTOM
            st.session_state[keys.slot_hex(i)] = p.hex
        st.rerun()

    # --- Palette slots (dark to light) ---
    # Seed "n" before the slider widget is created so the widget can own the value via key=
    # without a conflicting value= argument causing a session_state warning.
    st.session_state.setdefault(keys.N, 5)
    n = st.slider("Number of layers", 3, 7, key=keys.N)

    # --- Generate from midtone ---
    with st.expander("Generate from midtone colour"):
        mid_hex = st.color_picker("Midtone (base colour)", value="#808080", key=keys.MIDTONE_HEX)
        mid_hexes = ramp_from_midtone(mid_hex, n)
        mid_paints = [
            collection.nearest_paint(PaintColor(f"m{i}", h).rgb, context.CATALOG)
            for i, h in enumerate(mid_hexes)
        ]
        band_cols = st.columns(n)
        for i, (h, p, col) in enumerate(zip(mid_hexes, mid_paints, band_cols)):
            col.markdown(helpers.swatch(h, size="2.2em"), unsafe_allow_html=True)
            if p:
                col.caption(p.name)
        apply_col, save_col = st.columns(2)
        if apply_col.button("Apply", key=keys.GENERATE_RAMP):
            for i, h in enumerate(mid_hexes):
                st.session_state[keys.slot_hex(i)] = h
                st.session_state[keys.slot_code(i)] = context.CUSTOM
            st.rerun()
        if save_col.button("💾 Save", key="save_midtone_ramp"):
            steps = [
                RecipeStep(label=r, hex=h, paint_ref=(p.name if p else None))
                for r, h, p in zip(role_names(n), mid_hexes, mid_paints)
            ]
            recipe_name = f"Midtone ({mid_hex})"
            save_user(Recipe(recipe_name, steps))
            st.toast(f"Saved '{recipe_name}'")

    # --- Colour variants ---
    with st.expander("🎨 Colour variants"):
        mid = st.session_state.get(keys.MIDTONE_HEX, "#808080")
        variants = [
            ("Complementary", hue_rotate(mid, 180)),
            ("Warm analogous", hue_rotate(mid, 30)),
            ("Cool analogous", hue_rotate(mid, -30)),
        ]
        for idx, (label, base_hex) in enumerate(variants):
            hexes = ramp_from_midtone(base_hex, n)
            paints = [
                collection.nearest_paint(PaintColor(f"v{i}", h).rgb, context.CATALOG)
                for i, h in enumerate(hexes)
            ]

            head_col, btn_col1, btn_col2 = st.columns([3, 1, 1])
            head_col.markdown(f"**{label}**")
            if btn_col1.button("Apply", key=f"apply_variant_{label}"):
                for i, h in enumerate(hexes):
                    st.session_state[keys.slot_hex(i)] = h
                    st.session_state[keys.slot_code(i)] = context.CUSTOM
                st.rerun()
            if btn_col2.button("💾 Save", key=f"save_variant_{label}"):
                steps = [
                    RecipeStep(label=r, hex=h, paint_ref=(p.name if p else None))
                    for r, h, p in zip(role_names(n), hexes, paints)
                ]
                recipe_name = f"{label} ({mid})"
                save_user(Recipe(recipe_name, steps))
                st.toast(f"Saved '{recipe_name}'")

            band_cols = st.columns(n)
            for i, (h, p, col) in enumerate(zip(hexes, paints, band_cols)):
                col.markdown(helpers.swatch(h, size="2.2em"), unsafe_allow_html=True)
                if p:
                    col.caption(p.name)

            if idx < len(variants) - 1:
                st.divider()

    st.markdown("**Palette** (dark to light)")
    palette = []
    options = context.CATALOG_CODES + [context.CUSTOM]
    for i in range(n):
        if i < len(DEFAULT_PALETTE):
            default = DEFAULT_PALETTE[i]
        else:
            default = PaintColor(f"Grey {i + 1}", ramp_hex(i, n))
        st.session_state.setdefault(keys.slot_code(i), default.code)
        st.session_state.setdefault(keys.slot_hex(i), default.hex)
        default_code = st.session_state[keys.slot_code(i)]
        if default_code != context.CUSTOM and find_by_code(context.CATALOG, default_code) is None:
            default_code = context.CUSTOM
        c1, c2, c3 = st.columns([3, 1, 1])
        slot_sel = c1.selectbox(
            f"Layer {i + 1}", options,
            index=options.index(default_code),
            format_func=lambda c: context.CUSTOM if c == context.CUSTOM else context.CODE_LABEL.get(c, c),
            key=keys.slot_code(i),
        )
        if slot_sel == context.CUSTOM:
            hexv = c2.color_picker(
                f"hex {i + 1}", key=keys.slot_hex(i), label_visibility="collapsed",
            )
            pasted = c3.text_input(
                f"paste hex {i + 1}", value=hexv, key=keys.slot_hexinput(i),
                on_change=_apply_paste_hex, args=(i,), label_visibility="collapsed",
            )
            if pasted and valid_hex(pasted) is None:
                c3.caption("⚠️ invalid hex")
            paint = PaintColor(f"Custom {i + 1}", hexv)
            palette.append(paint)
            near = collection.nearest_paint(paint.rgb, context.CATALOG)
            if near is not None:
                owned_badge = "✅ owned" if near.code in set(picked) else "⚠️ not owned"
                c3.caption(f"{hexv} · closest: {near.name} · {near.code} ({owned_badge})")
        else:
            paint = find_by_code(context.CATALOG, slot_sel)
            c2.markdown(helpers.swatch(paint.hex, size="2.2em"), unsafe_allow_html=True)
            palette.append(paint)
            st.session_state[keys.slot_hex(i)] = paint.hex
            badge = "✅ owned" if paint.code in set(picked) else "⚠️ not owned"
            c3.write(f"{paint.hex} · {badge}")

        # Interior slots can be filled with the Lab-midpoint of their neighbours.
        if 0 < i < n - 1:
            c1.button("↕ blend neighbours", key=keys.blend(i),
                      on_click=_blend_neighbours, args=(i, n))

    return palette, n


def render_save_recipe(palette, n) -> None:
    """Render the 'Save as recipe' expander."""
    with st.expander("Save as recipe"):
        rname = st.text_input("Recipe name", key=keys.SAVE_NAME)
        if st.button("Save recipe") and rname.strip():
            steps = [RecipeStep(label=r, hex=p.hex, paint_ref=(p.name if p.code else None))
                     for r, p in zip(role_names(n), palette)]
            save_user(Recipe(rname.strip(), steps))
            st.success(f"Saved recipe '{rname.strip()}'.")
