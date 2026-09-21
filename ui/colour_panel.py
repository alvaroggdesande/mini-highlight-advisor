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
from mini_highlight_advisor.recipes import (
    load_all, load_user, to_palette, save_user,
    export_to_json_bytes, import_from_json_bytes,
    Recipe, RecipeStep,
)
from mini_highlight_advisor.matching import match, Target
from i18n import t
from ui import context, coverage_editor, helpers, keys


def _reseed_editor_widgets() -> None:
    st.session_state.pop(keys.LOADED_G, None)
    st.session_state.pop(keys.COV_N, None)
    for k in [k for k in list(st.session_state)
              if k.startswith("slot_code_") or k.startswith("slot_hex_")
              or k.startswith("slot_hexinput_") or k.startswith("cov_pct_")]:
        st.session_state.pop(k, None)


def _render_level1(book, owned_paints) -> None:
    """Level 1 — whole-mini scheme: surfaces + hero + mood → generate & apply."""
    # Pre-fill from stored colour decisions (only when session keys are absent)
    if book.hero_hex is not None and "sgen_anchor_hex" not in st.session_state:
        st.session_state["sgen_anchor_hex"] = book.hero_hex
    if book.mood is not None and book.mood in MOODS and "sgen_mood" not in st.session_state:
        st.session_state["sgen_mood"] = book.mood
    generated = st.session_state.get(keys.SCHEME_GENERATED, False)
    with st.expander(t("colour.scheme_expander"), expanded=not generated):
        names = book.names()
        st.caption(t("colour.scheme_caption"))
        for g, name in enumerate(names):
            c1, c2 = st.columns([1, 1])
            surf_keys = list(SURFACES)
            cur_surf = book.surface_at(g)
            idx = surf_keys.index(cur_surf) if cur_surf in surf_keys else surf_keys.index("other")
            chosen = c1.selectbox(
                t("colour.surface_label", name=name), surf_keys, index=idx,
                format_func=lambda s: SURFACES[s].display, key=f"sgen_surface_{g}")
            book.set_surface_at(g, chosen)
            spec = get_surface(chosen)
            if spec.bucket == REALISTIC:
                tone_opts = list(spec.tones) + [HARMONY_TONE]
                cur_tone = book.tone_at(g)
                t_idx = tone_opts.index(cur_tone) if cur_tone in tone_opts else 0
                tone = c2.selectbox(
                    t("colour.tone_label", name=name), tone_opts, index=t_idx,
                    format_func=lambda tone_v: t("colour.tone_follow_scheme") if tone_v == HARMONY_TONE else tone_v,
                    key=f"sgen_tone_{g}")
                book.set_tone_at(g, tone)
            else:
                book.set_tone_at(g, None)

        anchor_name = st.selectbox(t("colour.hero_region_label"), names, key="sgen_anchor")
        g_anchor = names.index(anchor_name)
        pal = book.palette_at(g_anchor)
        default_hex = pal[len(pal) // 2].hex if pal else "#c02030"
        anchor_hex = st.color_picker(t("colour.hero_colour_label"), value=default_hex, key="sgen_anchor_hex")
        mood = st.selectbox(t("colour.mood_label"), list(MOODS), key="sgen_mood")
        variant = st.selectbox(t("colour.harmony_label"), VARIANTS, key="sgen_variant",
                               help=t("colour.harmony_help"))
        owned_only = st.checkbox(t("colour.owned_only_cb"), value=False,
                                 key="sgen_owned_only")
        set_tech = st.checkbox(t("colour.set_tech_cb"), value=True,
                               key="sgen_set_tech")

        if st.button(t("colour.generate_btn"), type="primary", key="sgen_go"):
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
            book.hero_hex = anchor_hex
            book.mood = mood
            st.session_state[keys.SCHEME_GENERATED] = True
            _reseed_editor_widgets()
            st.success(t("colour.generated_success"))
            st.rerun()


_RECIPE_IMPORT_NONCE = "_recipe_import_nonce"


def _render_recipe_manager() -> None:
    with st.expander(t("colour.manage_recipes_expander")):
        user_recipes = load_user()
        if user_recipes:
            st.download_button(
                t("colour.download_recipes_btn"),
                data=export_to_json_bytes(user_recipes),
                file_name="my_recipes.json",
                mime="application/json",
                key="_recipe_dl_btn",
            )

        nonce = st.session_state.get(_RECIPE_IMPORT_NONCE, 0)
        uploader_key = f"_recipe_import_{nonce}"

        def _on_import():
            uploaded = st.session_state.get(uploader_key)
            if uploaded is None:
                return
            try:
                imported = import_from_json_bytes(uploaded.read())
                for r in imported:
                    save_user(r)
                st.session_state[_RECIPE_IMPORT_NONCE] = nonce + 1
                st.session_state["_recipe_import_count"] = len(imported)
            except Exception as exc:
                st.session_state["_recipe_import_err"] = str(exc)

        st.file_uploader(
            t("colour.import_recipes_label"),
            type=["json"],
            key=uploader_key,
            on_change=_on_import,
        )
        if count := st.session_state.pop("_recipe_import_count", None):
            st.toast(t("colour.recipes_imported_toast", count=count))
        if err := st.session_state.pop("_recipe_import_err", None):
            st.error(t("colour.import_recipes_error", err=err))


def _apply_ramp(hexes: list[str], n: int) -> None:
    """Write a list of hex strings into the palette-slot session keys."""
    for i, h in enumerate(hexes[:n]):
        st.session_state[keys.slot_hex(i)] = h
        st.session_state[keys.slot_code(i)] = context.CUSTOM
    st.session_state["_ramp_applied"] = True


def _write_ramp_decision(book, sel: int, mid_hex: str, variant: str) -> None:
    """Persist the ramp decision (midtone hex + variant key) on the book."""
    if sel > 0:
        book.drawn[sel - 1].ramp_midtone = mid_hex
        book.drawn[sel - 1].ramp_variant = variant
    else:
        book.whole_ramp_midtone = mid_hex
        book.whole_ramp_variant = variant


def _render_level2(book, sel: int, n: int, owned_paints) -> None:
    """Level 2 — region ramp: midtone → ramp + harmony variants.

    Applies immediately on button click (no preview thumbnail — left-column
    render is the preview).
    """
    _VARIANT_MAP = {"Ramp": "standard", "Complementary": "complementary",
                    "Warm (+30°)": "warm", "Cool (−30°)": "cool"}

    st.divider()
    st.markdown(t("colour.ramp_heading", name=book.names()[sel]))

    # Resolve ramp decisions for whichever region is selected.
    _ramp_midtone = book.drawn[sel - 1].ramp_midtone if sel > 0 else book.whole_ramp_midtone
    _ramp_variant = book.drawn[sel - 1].ramp_variant if sel > 0 else book.whole_ramp_variant

    # Pre-fill midtone picker from stored ramp decision (only when session key absent)
    if _ramp_midtone is not None and keys.midtone_hex(sel) not in st.session_state:
        st.session_state[keys.midtone_hex(sel)] = _ramp_midtone

    # Last-applied indicator
    if _ramp_variant is not None:
        _variant_labels = {
            "standard": t("colour.ramp_btn"),
            "complementary": t("colour.complementary_btn"),
            "warm": t("colour.warm_btn"),
            "cool": t("colour.cool_btn"),
        }
        _applied_label = _variant_labels.get(_ramp_variant, _ramp_variant)
        st.caption(t("colour.last_applied", label=_applied_label))

    # Scheme shortcut: seed the midtone picker with the midtone of this region's
    # palette, which is the colour the scheme assigned to it.  Works uniformly
    # for whole-mini (sel==0) and all drawn regions — no hue-rotate needed.
    if book.hero_hex is not None:
        _pal = book.palette_at(sel)
        _anchor_hex = _pal[len(_pal) // 2].hex
        c_info, c_btn = st.columns([3, 1])
        c_info.caption(
            t("colour.scheme_colour", swatch=helpers.swatch(_anchor_hex, size='1.2em'), hex=_anchor_hex),
            unsafe_allow_html=True,
        )
        if c_btn.button(t("colour.use_btn"), key=f"use_complement_{sel}"):
            st.session_state[keys.midtone_hex(sel)] = _anchor_hex
            st.rerun()

    mid_hex = st.color_picker(t("colour.midtone_label"), value="#808080", key=keys.midtone_hex(sel))

    ramps = {
        t("colour.ramp_btn"):          ("standard",      ramp_from_midtone(mid_hex, n)),
        t("colour.complementary_btn"): ("complementary", ramp_from_midtone(hue_rotate(mid_hex, 180), n)),
        t("colour.warm_btn"):          ("warm",          ramp_from_midtone(hue_rotate(mid_hex, 30), n)),
        t("colour.cool_btn"):          ("cool",          ramp_from_midtone(hue_rotate(mid_hex, -30), n)),
    }

    btn_cols = st.columns(len(ramps))
    for col, (label, (variant_key, hexes)) in zip(btn_cols, ramps.items()):
        if col.button(label, key=f"apply_ramp_{label}", width="stretch"):
            _apply_ramp(hexes, n)
            _write_ramp_decision(book, sel, mid_hex, variant_key)


def _apply_paste_hex(i: int) -> None:
    norm = valid_hex(st.session_state.get(keys.slot_hexinput(i), ""))
    if norm is not None:
        st.session_state[keys.slot_hex(i)] = norm


def _blend_neighbours(i: int, n: int) -> None:
    from mini_highlight_advisor.color import blend_hex_lab
    lo = st.session_state.get(keys.slot_hex(i - 1), "#000000") if i > 0 else "#000000"
    hi = st.session_state.get(keys.slot_hex(i + 1), "#ffffff") if i < n - 1 else "#ffffff"
    st.session_state[keys.slot_hex(i)] = blend_hex_lab(lo, hi)
    st.session_state[keys.slot_code(i)] = context.CUSTOM


def _delete_band_at(i: int, n: int) -> None:
    """Delete band i, shift bands i+1..n-1 down, decrement n. No-op if n <= 3."""
    if n <= 3:
        return
    for j in range(i, n - 1):
        st.session_state[keys.slot_code(j)] = st.session_state.get(keys.slot_code(j + 1))
        st.session_state[keys.slot_hex(j)] = st.session_state.get(keys.slot_hex(j + 1))
        st.session_state[keys.slot_hexinput(j)] = st.session_state.get(keys.slot_hexinput(j + 1), "")
    last = n - 1
    st.session_state.pop(keys.slot_code(last), None)
    st.session_state.pop(keys.slot_hex(last), None)
    st.session_state.pop(keys.slot_hexinput(last), None)
    st.session_state[keys.N] = n - 1


def _remove_last_band(n: int) -> None:
    """Remove the last band (position n-1), decrement N. No-op if n <= 3."""
    if n <= 3:
        return
    st.session_state.pop(keys.slot_code(n - 1), None)
    st.session_state.pop(keys.slot_hex(n - 1), None)
    st.session_state.pop(keys.slot_hexinput(n - 1), None)
    st.session_state[keys.N] = n - 1


def _add_band(n: int) -> None:
    """Append a new lightest band at position n, increment N. No-op if n >= 7."""
    if n >= 7:
        return
    st.session_state[keys.slot_hex(n)] = ramp_hex(n, n + 1)
    st.session_state[keys.slot_code(n)] = context.CUSTOM
    st.session_state[keys.N] = n + 1


def _insert_band_at_start(n: int) -> None:
    """Insert a new darkest band at position 0, shifting all others up. No-op if n >= 7."""
    if n >= 7:
        return
    for j in range(n - 1, -1, -1):
        st.session_state[keys.slot_code(j + 1)] = st.session_state.get(keys.slot_code(j))
        st.session_state[keys.slot_hex(j + 1)] = st.session_state.get(keys.slot_hex(j))
        st.session_state.pop(keys.slot_hexinput(j + 1), None)
    st.session_state[keys.slot_hex(0)] = ramp_hex(0, n + 1)
    st.session_state[keys.slot_code(0)] = context.CUSTOM
    st.session_state.pop(keys.slot_hexinput(0), None)
    st.session_state[keys.N] = n + 1


def _insert_band_after(i: int, n: int) -> None:
    """Insert a new band after position i, shift i+1..n-1 up, increment n. No-op if n >= 7."""
    from mini_highlight_advisor.color import blend_hex_lab
    if n >= 7:
        return
    for j in range(n - 1, i, -1):
        st.session_state[keys.slot_code(j + 1)] = st.session_state.get(keys.slot_code(j))
        st.session_state[keys.slot_hex(j + 1)] = st.session_state.get(keys.slot_hex(j))
        st.session_state.pop(keys.slot_hexinput(j + 1), None)
    lo = st.session_state.get(keys.slot_hex(i), ramp_hex(i, n))
    if i < n - 1:
        hi = st.session_state.get(keys.slot_hex(i + 2), ramp_hex(i + 2, n + 1))
        new_hex = blend_hex_lab(lo, hi)
    else:
        new_hex = ramp_hex(i + 1, n + 1)
    st.session_state[keys.slot_hex(i + 1)] = new_hex
    st.session_state[keys.slot_code(i + 1)] = context.CUSTOM
    st.session_state.pop(keys.slot_hexinput(i + 1), None)
    st.session_state[keys.N] = n + 1


def _render_level3(book, sel: int, picked) -> tuple[list[PaintColor], int]:
    """Level 3 — bands: palette slots dark→light with inline owned-first match.

    Returns (palette, n) so the caller can set book.set_palette_at(sel, palette).
    """
    st.divider()
    # Recipe loader
    recipes = load_all()
    recipe_by_name = {r.name: r for r in recipes}
    name_counts = Counter(p.name for p in context.CATALOG)
    _recipe_none = t("colour.recipe_none")
    choice = st.selectbox(t("colour.load_recipe_label"), [_recipe_none] + list(recipe_by_name),
                          key="cp_recipe_choice")
    if st.button(t("colour.load_recipe_btn"), key="cp_recipe_load") and choice != _recipe_none:
        pal = to_palette(recipe_by_name[choice])
        st.session_state[keys.N] = max(3, min(7, len(pal)))
        for i, p in enumerate(pal[:st.session_state[keys.N]]):
            _found = find_by_name(context.CATALOG, p.name)
            unique = name_counts.get(p.name) == 1
            st.session_state[keys.slot_code(i)] = _found.code if (_found and unique) else context.CUSTOM
            st.session_state[keys.slot_hex(i)] = p.hex
        # Defer the rerun instead of firing it here: an immediate st.rerun() aborts
        # this pass BEFORE render() commits the new slots to the book (set_palette_at),
        # so the next pass's analysis would still read the OLD palette and the preview
        # would lag one interaction. Falling through lets the slot widgets below pick
        # up these values and render() write them to the book; the deferred rerun at
        # the end of render() then repaints the preview from the updated book.
        st.session_state["_recipe_loaded"] = True

    st.session_state.setdefault(keys.N, 5)
    n = st.session_state[keys.N]
    c_hdr, c_ins_first = st.columns([4, 1])
    c_hdr.markdown(t("colour.bands_heading", n=n))
    c_ins_first.button("＋", key="band_ins_start", help=t("colour.insert_first_help"),
                       disabled=(n >= 7), on_click=_insert_band_at_start, args=(n,))

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
            t("colour.layer_label", i=i + 1), options,
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
                c3.caption(t("colour.invalid_hex"))
            paint = PaintColor(f"Custom {i+1}", hexv)
            palette.append(paint)
            _owned_list = [p for p in context.CATALOG if p.code and p.code in set(picked)]
            _finish = "metallic" if book.material_at(sel) == "nmm" else "matte"
            _result = match(Target(hexv, None, _finish), owned=_owned_list, catalog=list(context.CATALOG))
            c3.caption(_result.phrase)
        else:
            paint = find_by_code(context.CATALOG, slot_sel)
            c2.markdown(helpers.swatch(paint.hex, size="2.2em"), unsafe_allow_html=True)
            palette.append(paint)
            st.session_state[keys.slot_hex(i)] = paint.hex
            badge = t("colour.owned_badge") if paint.code in set(picked) else t("colour.not_owned_badge")
            c3.write(f"{paint.hex} · {badge}")

        ba, bb, bc = c1.columns(3)
        ba.button("✕", key=f"band_del_{i}", help=t("colour.delete_band_help"),
                  disabled=(n <= 3), on_click=_delete_band_at, args=(i, n))
        bb.button("↕", key=keys.blend(i), help=t("colour.blend_help"),
                  on_click=_blend_neighbours, args=(i, n))
        bc.button("＋", key=f"band_ins_{i}", help=t("colour.insert_below_help"),
                  disabled=(n >= 7), on_click=_insert_band_after, args=(i, n))

    c_name, c_btn = st.columns([3, 1])
    save_name = c_name.text_input(t("colour.save_recipe_label"), key=f"band_recipe_name_{sel}",
                                   placeholder=t("colour.save_recipe_placeholder"),
                                   label_visibility="collapsed")
    c_name.caption(t("colour.save_recipe_caption"))
    if c_btn.button(t("colour.save_recipe_btn"), key=f"band_recipe_save_{sel}"):
        clean = save_name.strip()
        if not clean:
            st.warning(t("colour.recipe_name_required"))
        else:
            steps = [RecipeStep(label=role_names(n)[i], hex=p.hex,
                                paint_ref=p.name if p.code else None)
                     for i, p in enumerate(palette)]
            save_user(Recipe(clean, steps))
            st.toast(t("colour.recipe_saved_toast", name=clean))

    return palette, n


def _render_scheme_save(book) -> None:
    """Scheme save / swap at the bottom of the Colour panel (replaces schemes_panel)."""
    st.divider()
    stored = st.session_state.setdefault(keys.SCHEMES, [])
    with st.expander(t("colour.schemes_expander")):
        name = st.text_input(t("colour.scheme_name_label"), key="cp_scheme_save_name")
        if st.button(t("colour.save_scheme_btn"), type="primary", key="cp_scheme_save_btn"):
            clean = name.strip()
            if not clean:
                st.warning(t("colour.scheme_name_required"))
            else:
                snap = sch.snapshot(book, clean)
                existing = next((s for s in stored if s.name == clean), None)
                if existing:
                    stored[stored.index(existing)] = snap
                    st.toast(t("colour.scheme_updated_toast", name=clean))
                else:
                    stored.append(snap)
                    st.toast(t("colour.scheme_saved_toast", name=clean))
                st.rerun()

        if stored:
            names = [s.name for s in stored]
            pick = st.radio(t("colour.saved_schemes_label"), names, key="cp_scheme_pick")
            chosen = stored[names.index(pick)]
            c_apply, c_del = st.columns(2)
            if c_apply.button(t("colour.apply_btn"), type="primary", key="cp_scheme_apply_btn"):
                report = sch.apply(chosen, book)
                _reseed_editor_widgets()
                if report.skipped_regions:
                    st.info(t("colour.scheme_applied_info",
                               count=len(report.updated),
                               skipped=', '.join(report.skipped_regions)))
                st.rerun()
            if c_del.button(t("colour.delete_btn"), key="cp_scheme_delete_btn"):
                stored.remove(chosen)
                st.session_state.pop("cp_scheme_pick", None)
                st.rerun()


def render(book, sel: int, picked, owned_paints, rgb=None) -> None:
    """Render the three-level colour panel for the selected region.

    Order: Bands (primary) → Coverage → Ramp → Scheme → Save.
    """
    st.markdown(t("colour.editing_heading", name=book.names()[sel]))

    # Level 3 first: bands are the primary interaction.
    palette, n = _render_level3(book, sel, picked)
    book.set_palette_at(sel, palette)

    # Coverage lives next to bands (both are about 'how many layers and how wide').
    st.divider()
    cov = coverage_editor.render(n)
    book.set_coverage_at(sel, cov)

    # Level 2: ramp quick-apply to seed the bands.
    _render_level2(book, sel, n, owned_paints)

    # Level 1: whole-mini scheme — collapsed once generated.
    _render_level1(book, owned_paints)

    # Scheme save / swap at the bottom.
    _render_scheme_save(book)
    _render_recipe_manager()

    # Deferred rerun after Apply Ramp / Load recipe so Level 3 has already updated
    # the book palette before the analysis re-runs — one click = one visible update.
    _deferred = st.session_state.pop("_ramp_applied", False)
    _deferred = st.session_state.pop("_recipe_loaded", False) or _deferred
    if _deferred:
        st.rerun()
