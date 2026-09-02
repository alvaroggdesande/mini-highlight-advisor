# ui/colour_panel.py
"""Three-level colour panel: whole-mini scheme → region ramp → bands.

Level 1 (whole-mini scheme) is implemented in this file.
Levels 2 and 3 are added in subsequent tasks.
"""
import streamlit as st

from mini_highlight_advisor import scheme_build as sb, schemes as sch
from mini_highlight_advisor.scheme_gen import RegionColorSpec, MOODS, VARIANTS, HARMONY_TONE
from mini_highlight_advisor.surfaces import SURFACES, get_surface, REALISTIC
from ui import context, keys


def _reseed_editor_widgets() -> None:
    """Drop widget keys for palette slots so the editor re-seeds from the book."""
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


def render(book, sel: int, picked, owned_paints) -> None:
    """Render the three-level colour panel for the given region selection.

    Levels 2 and 3 are stubs until Tasks 6 and 7 add them.
    """
    _render_level1(book, owned_paints)
    # Level 2 and 3 will be inserted here in subsequent tasks.
