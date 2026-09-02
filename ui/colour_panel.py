# ui/colour_panel.py
"""Three-level colour panel: whole-mini scheme → region ramp → bands + inline match."""
import streamlit as st
from collections import Counter

from mini_highlight_advisor import scheme_build as sb, schemes as sch
from mini_highlight_advisor.scheme_gen import RegionColorSpec, MOODS, VARIANTS, HARMONY_TONE
from mini_highlight_advisor.surfaces import SURFACES, get_surface, REALISTIC
from mini_highlight_advisor.palette import (
    DEFAULT_PALETTE, PaintColor, role_names, ramp_hex, valid_hex,
)
from mini_highlight_advisor.color import hue_rotate, ramp_from_midtone
from mini_highlight_advisor.catalog import find_by_code, find_by_name
from mini_highlight_advisor.recipes import load_all, to_palette, save_user, Recipe, RecipeStep
from mini_highlight_advisor import collection
from ui import context, helpers, keys


def _reseed_editor_widgets() -> None:
    st.session_state.pop(keys.LOADED_G, None)
    st.session_state.pop(keys.COV_N, None)
    for k in [k for k in list(st.session_state)
              if k.startswith("slot_code_") or k.startswith("slot_hex_")
              or k.startswith("slot_hexinput_") or k.startswith("cov_pct_")]:
        st.session_state.pop(k, None)


def _render_level1(book, owned_paints) -> None:
    """Level 1 — whole-mini scheme: surfaces + hero + mood → generate & apply."""
    generated = st.session_state.get(keys.SCHEME_GENERATED, False)
    with st.expander("🎯 Generate scheme (surfaces + hero colour + mood)",
                     expanded=not generated):
        names = book.names()
        st.caption("Tag each region, then pick a hero colour and a mood.")
        for g, name in enumerate(names):
            c1, c2 = st.columns([1, 1])
            surf_keys = list(SURFACES)
            cur_surf = book.surface_at(g)
            idx = surf_keys.index(cur_surf) if cur_surf in surf_keys else surf_keys.index("other")
            chosen = c1.selectbox(
                f"Surface — {name}", surf_keys, index=idx,
                format_func=lambda s: SURFACES[s].display, key=f"sgen_surface_{g}")
            book.set_surface_at(g, chosen)
            spec = get_surface(chosen)
            if spec.bucket == REALISTIC:
                tone_opts = list(spec.tones) + [HARMONY_TONE]
                cur_tone = book.tone_at(g)
                t_idx = tone_opts.index(cur_tone) if cur_tone in tone_opts else 0
                tone = c2.selectbox(
                    f"Tone — {name}", tone_opts, index=t_idx,
                    format_func=lambda t: "Follow scheme colour" if t == HARMONY_TONE else t,
                    key=f"sgen_tone_{g}")
                book.set_tone_at(g, tone)
            else:
                book.set_tone_at(g, None)

        anchor_name = st.selectbox("Hero region (anchor)", names, key="sgen_anchor")
        g_anchor = names.index(anchor_name)
        pal = book.palette_at(g_anchor)
        default_hex = pal[len(pal) // 2].hex if pal else "#c02030"
        anchor_hex = st.color_picker("Hero colour", value=default_hex, key="sgen_anchor_hex")
        mood = st.selectbox("Mood", list(MOODS), key="sgen_mood")
        variant = st.selectbox("Harmony", VARIANTS, key="sgen_variant",
                               help="Cycle this to re-roll the free regions' colours.")
        owned_only = st.checkbox("Owned only (no catalogue suggestions)", value=False,
                                 key="sgen_owned_only")
        set_tech = st.checkbox("Also set techniques from surface", value=True,
                               key="sgen_set_tech")

        if st.button("✨ Generate & apply scheme", type="primary", key="sgen_go"):
            specs = [
                RegionColorSpec(nm, book.surface_at(g), book.tone_at(g),
                                len(book.palette_at(g)))
                for g, nm in enumerate(names)
            ]
            scheme = sb.build_scheme(
                "Generated", specs, anchor_name, anchor_hex, mood, variant,
                list(owned_paints), list(context.CATALOG), owned_only)
            sch.apply(scheme, book)
            if set_tech:
                ps_on = st.session_state.get(keys.NORMALS) is not None
                for g, nm in enumerate(names):
                    tech = get_surface(book.surface_at(g)).default_technique
                    if not tech:
                        continue
                    if tech == "nmm" and not ps_on:
                        continue
                    book.set_material_at(g, tech)
            st.session_state[keys.SCHEME_GENERATED] = True
            _reseed_editor_widgets()
            st.success("Scheme generated and applied. Adjust any colour below.")
            st.rerun()


def _apply_ramp(hexes: list[str], n: int) -> None:
    """Write a list of hex strings into the palette-slot session keys."""
    for i, h in enumerate(hexes[:n]):
        st.session_state[keys.slot_hex(i)] = h
        st.session_state[keys.slot_code(i)] = context.CUSTOM


def _render_level2(book, sel: int, n: int, owned_paints) -> None:
    """Level 2 — region ramp: midtone → ramp + harmony variants.

    Applies immediately on button click (no preview thumbnail — left-column
    render is the preview).
    """
    st.divider()
    st.markdown(f"**Ramp for: {book.names()[sel]}**")

    mid_hex = st.color_picker("Base colour (midtone)", value="#808080", key=keys.MIDTONE_HEX)

    ramps = {
        "Ramp": ramp_from_midtone(mid_hex, n),
        "Complementary": ramp_from_midtone(hue_rotate(mid_hex, 180), n),
        "Warm (+30°)":   ramp_from_midtone(hue_rotate(mid_hex, 30), n),
        "Cool (−30°)":   ramp_from_midtone(hue_rotate(mid_hex, -30), n),
    }

    for label, hexes in ramps.items():
        paints = [
            collection.nearest_paint(PaintColor(f"r{i}", h).rgb, context.CATALOG)
            for i, h in enumerate(hexes)
        ]
        row_cols = st.columns([2] + [1] * n)
        row_cols[0].markdown(f"**{label}**")
        for i, (h, p) in enumerate(zip(hexes, paints)):
            row_cols[i + 1].markdown(helpers.swatch(h, size="1.8em"), unsafe_allow_html=True)
            if p:
                row_cols[i + 1].caption(p.name[:10])

        apply_col, save_col = st.columns(2)
        if apply_col.button(f"Apply {label}", key=f"apply_ramp_{label}"):
            _apply_ramp(hexes, n)
            st.rerun()
        if save_col.button(f"💾 Save", key=f"save_ramp_{label}"):
            steps = [
                RecipeStep(label=r, hex=h, paint_ref=(p.name if p else None))
                for r, h, p in zip(role_names(n), hexes, paints)
            ]
            save_user(Recipe(f"{label} ({mid_hex})", steps))
            st.toast(f"Saved '{label} ({mid_hex})'")


def _apply_paste_hex(i: int) -> None:
    norm = valid_hex(st.session_state.get(keys.slot_hexinput(i), ""))
    if norm is not None:
        st.session_state[keys.slot_hex(i)] = norm


def _blend_neighbours(i: int, n: int) -> None:
    from mini_highlight_advisor.color import blend_hex_lab
    lo = st.session_state.get(keys.slot_hex(i - 1), ramp_hex(i - 1, n))
    hi = st.session_state.get(keys.slot_hex(i + 1), ramp_hex(i + 1, n))
    st.session_state[keys.slot_hex(i)] = blend_hex_lab(lo, hi)
    st.session_state[keys.slot_code(i)] = context.CUSTOM


def _render_level3(book, sel: int, picked) -> tuple[list[PaintColor], int]:
    """Level 3 — bands: palette slots dark→light with inline owned-first match.

    Returns (palette, n) so the caller can set book.set_palette_at(sel, palette).
    """
    st.divider()
    # Recipe loader
    recipes = load_all()
    recipe_by_name = {r.name: r for r in recipes}
    name_counts = Counter(p.name for p in context.CATALOG)
    choice = st.selectbox("Load recipe", ["(none)"] + list(recipe_by_name),
                          key="cp_recipe_choice")
    if st.button("Load recipe", key="cp_recipe_load") and choice != "(none)":
        pal = to_palette(recipe_by_name[choice])
        st.session_state[keys.N] = max(3, min(7, len(pal)))
        for i, p in enumerate(pal[:st.session_state[keys.N]]):
            match = find_by_name(context.CATALOG, p.name)
            unique = name_counts.get(p.name) == 1
            st.session_state[keys.slot_code(i)] = match.code if (match and unique) else context.CUSTOM
            st.session_state[keys.slot_hex(i)] = p.hex
        st.rerun()

    st.session_state.setdefault(keys.N, 5)
    n = st.slider("Number of layers", 3, 7, key=keys.N)

    st.markdown("**Bands (dark → light)**")
    palette = []
    options = context.CATALOG_CODES + [context.CUSTOM]
    for i in range(n):
        default = DEFAULT_PALETTE[i] if i < len(DEFAULT_PALETTE) else PaintColor(f"Grey {i+1}", ramp_hex(i, n))
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
            hexv = c2.color_picker(f"hex {i+1}", key=keys.slot_hex(i),
                                   label_visibility="collapsed")
            pasted = c3.text_input(f"paste hex {i+1}", value=hexv, key=keys.slot_hexinput(i),
                                   on_change=_apply_paste_hex, args=(i,),
                                   label_visibility="collapsed")
            if pasted and valid_hex(pasted) is None:
                c3.caption("⚠️ invalid hex")
            paint = PaintColor(f"Custom {i+1}", hexv)
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

        if 0 < i < n - 1:
            c1.button("↕ blend", key=keys.blend(i),
                      on_click=_blend_neighbours, args=(i, n))

    return palette, n


def _render_scheme_save(book) -> None:
    """Scheme save / swap at the bottom of the Colour panel (replaces schemes_panel)."""
    st.divider()
    stored = st.session_state.setdefault(keys.SCHEMES, [])
    with st.expander("💾 Save & swap schemes"):
        name = st.text_input("Scheme name", key="cp_scheme_save_name")
        if st.button("＋ Save current as scheme", type="primary", key="cp_scheme_save_btn"):
            clean = name.strip()
            if not clean:
                st.warning("Give the scheme a name.")
            else:
                snap = sch.snapshot(book, clean)
                existing = next((s for s in stored if s.name == clean), None)
                if existing:
                    stored[stored.index(existing)] = snap
                    st.toast(f'Updated scheme "{clean}".')
                else:
                    stored.append(snap)
                    st.toast(f'Saved scheme "{clean}".')
                st.rerun()

        if stored:
            names = [s.name for s in stored]
            pick = st.radio("Saved schemes", names, key="cp_scheme_pick")
            chosen = stored[names.index(pick)]
            c_apply, c_del = st.columns(2)
            if c_apply.button("Apply", type="primary", key="cp_scheme_apply_btn"):
                report = sch.apply(chosen, book)
                _reseed_editor_widgets()
                if report.skipped_regions:
                    st.info(f"{len(report.updated)} region(s) updated — no saved colour "
                            f"for: {', '.join(report.skipped_regions)}")
                st.rerun()
            if c_del.button("Delete", key="cp_scheme_delete_btn"):
                stored.remove(chosen)
                st.session_state.pop("cp_scheme_pick", None)
                st.rerun()


def render(book, sel: int, picked, owned_paints) -> None:
    """Render the three-level colour panel for the selected region."""
    _render_level1(book, owned_paints)

    # Level 2 needs n (band count); read from session_state (set by Level 3 slider).
    n = st.session_state.get(keys.N, 5)
    _render_level2(book, sel, n, owned_paints)

    palette, n = _render_level3(book, sel, picked)
    book.set_palette_at(sel, palette)

    _render_scheme_save(book)
