import os
from collections import Counter

import streamlit as st

from mini_highlight_advisor.catalog import load_catalog, find_by_name, find_by_code
from mini_highlight_advisor import collection
from mini_highlight_advisor.palette import (
    DEFAULT_PALETTE, PaintColor, role_names, ramp_hex,
    default_coverage, remainder_pct, slider_max_pct, default_ramp, valid_hex,
)
from mini_highlight_advisor.color import blend_hex_lab
from mini_highlight_advisor.pipeline import prepare_shading, analyze_regions
from mini_highlight_advisor.recipes import load_all, to_palette, save_user, Recipe, RecipeStep
from mini_highlight_advisor.advisor import advise
from mini_highlight_advisor.matching import target_from_paint, target_from_hex
from mini_highlight_advisor.regions import Region, scale_points, polygon_to_mask, polygons_to_mask
from mini_highlight_advisor.overlay import swatch_board
from mini_highlight_advisor.region_state import RegionBook, new_book
from mini_highlight_advisor.input_check import check_input, SHOOTING_GUIDE, PAINTED_CAPTURE_NOTE
from ui import geometry, helpers
from PIL import Image


def _patch_image_to_url() -> None:
    # streamlit-drawable-canvas 0.9.3 calls the private helper
    # streamlit.elements.image.image_to_url(image, width, ...), which newer
    # Streamlit moved to streamlit.elements.lib.image_utils.image_to_url and
    # changed the 2nd arg from `width: int` to `layout_config` (only `.width`
    # is read). Re-expose an adapter so the component works unmodified. Pinned
    # to streamlit 1.61.* in requirements.txt; revisit on a major upgrade.
    import streamlit.elements.image as _si
    if hasattr(_si, "image_to_url"):
        return
    try:
        from types import SimpleNamespace
        from streamlit.elements.lib import image_utils as _iu

        def image_to_url(image, width, clamp, channels, output_format, image_id):
            return _iu.image_to_url(
                image, SimpleNamespace(width=width), clamp, channels, output_format, image_id
            )

        _si.image_to_url = image_to_url
    except Exception:
        pass  # leave unpatched -> st_canvas import/use degrades, single-palette still works


_patch_image_to_url()

try:
    from streamlit_drawable_canvas import st_canvas
except Exception:  # component missing/incompatible -> region drawing off, single-palette still works
    st_canvas = None

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


st.set_page_config(page_title="Mini Highlight Advisor", layout="wide")
st.title("Mini Highlight Advisor")
st.caption(
    "Upload a photo of a primed miniature (background-removed PNG is fastest). "
    "You'll get a painted preview + a paint-by-layer plan. Best with a raking "
    "side light (not on-axis flash) — that gives the sculpt the shadows the tool reads."
)

CATALOG = load_catalog()
CUSTOM = "(custom target)"
CODE_LABEL = {p.code: f"{p.name} · {p.paint_range or ''} · {p.code}" for p in CATALOG}
CATALOG_CODES = [p.code for p in CATALOG]


def _apply_paste_hex(i: int) -> None:
    # Runs on the paste field's change, before the rerun, on committed state.
    # Apply a pasted hex to the slot's colour only when the user edited the field
    # (never on every rerun), so it can't clobber a colour-picker drag or a blend.
    norm = valid_hex(st.session_state.get(f"slot_hexinput_{i}", ""))
    if norm is not None:
        st.session_state[f"slot_hex_{i}"] = norm


def _blend_neighbours(i: int, n: int) -> None:
    # Fill interior slot i with the Lab-midpoint of its neighbours. Runs as a
    # button on_click callback — BEFORE the rerun instantiates the slot widgets —
    # so writing slot_hex_{i}/slot_code_{i} is allowed (writing them in the loop
    # body, after the selectbox/picker are instantiated, raises StreamlitAPIException).
    lo = st.session_state.get(f"slot_hex_{i - 1}", ramp_hex(i - 1, n))
    hi = st.session_state.get(f"slot_hex_{i + 1}", ramp_hex(i + 1, n))
    st.session_state[f"slot_hex_{i}"] = blend_hex_lab(lo, hi)
    st.session_state[f"slot_code_{i}"] = CUSTOM




tab_mini, tab_paints = st.tabs(["🖌️ Miniature", "🎨 Paints"])

# NOTE: st.tabs runs BOTH bodies every rerun, in code order. Fill the Paints
# tab FIRST so owned_codes / owned_paints are finalised before the Miniature
# tab renders its ownership badges. Display order (Miniature first) is fixed by
# the label list above, not by code order — do not reorder the labels.

# --- 🎨 Paints tab: inventory ---
with tab_paints:
    st.markdown("**My paints** (Vallejo)")
    owned_codes = collection.load(catalog=CATALOG)
    picked = st.multiselect(
        "Paints you own", CATALOG_CODES,
        default=sorted(owned_codes & set(CATALOG_CODES)),
        format_func=lambda c: CODE_LABEL.get(c, c),
        key="owned",
    )
    if set(picked) != owned_codes:
        collection.save(set(picked))
    owned_paints = [p for c in picked if (p := find_by_code(CATALOG, c)) is not None]

    st.markdown("**Owned paints**")
    if not owned_paints:
        st.caption("No paints selected yet — tick the paints you own above.")
    for p in owned_paints:
        rng = p.paint_range or ""
        st.markdown(f"{helpers.swatch(p.hex)}{p.name} · {rng} · {p.code}", unsafe_allow_html=True)

    st.caption(f"Catalogue: {len(CATALOG)} paints (Vallejo Model Color + Game Color)")

# --- 🖌️ Miniature tab: region-centric editor ---
with tab_mini:
    if "book" not in st.session_state:
        st.session_state["book"] = new_book(5)
    book: RegionBook = st.session_state["book"]

    uploaded = st.file_uploader("Mini photo", type=["png", "jpg", "jpeg"])
    if uploaded is None:
        st.info("Upload a photo of a primed miniature to begin.")
        st.stop()

    suffix = os.path.splitext(uploaded.name)[1]
    try:
        with st.spinner("Preparing shading (first run downloads the depth model if no alpha channel)..."):
            rgb, alpha, shading = helpers.shading(uploaded.getvalue(), suffix)
        src_h, src_w = rgb.shape[:2]

        # Display geometry for the drawing canvas — computed once so both the
        # left (canvas) and right (Add-region handler) columns can use it.
        disp_w = min(600, src_w)
        disp_h = round(src_h * disp_w / src_w)
        draw_mode = st.session_state.get("draw_mode", False)

        left, right = st.columns([3, 2])
        with left:
            # In draw mode the big left panel IS the drawing surface (st_canvas
            # needs a wide, un-nested container to render — it collapses inside a
            # narrow column/expander). Otherwise show the read-only outline preview.
            if draw_mode and st_canvas is not None:
                st.caption("Trace a lasso around an area below, then click **Add region** on the right.")
                canvas = st_canvas(
                    fill_color="rgba(255,40,200,0.25)", stroke_width=2, stroke_color="#ff28c8",
                    background_image=Image.fromarray(rgb), height=disp_h, width=disp_w,
                    drawing_mode="freedraw", key=f"canvas_{len(book.drawn)}",
                )
            else:
                canvas = None
                outline = geometry.region_outline_image(rgb, book.drawn)
                st.image(outline, caption="Preview (region outlines)", use_container_width=True)
        with right:
            st.markdown("**Regions**")
            labels = book.names()
            sel = st.radio(
                "Select a region to edit", list(range(len(labels))),
                index=min(book.selected, len(labels) - 1),
                format_func=lambda g: labels[g], key="region_radio",
            )
            # On selection change, load that region's palette/coverage into widget keys.
            if st.session_state.get("_loaded_g") != sel:
                pal = book.palette_at(sel)
                cov = book.coverage_at(sel)
                st.session_state["n"] = len(pal)
                for i, p in enumerate(pal):
                    match = find_by_code(CATALOG, p.code) if p.code else None
                    st.session_state[f"slot_code_{i}"] = p.code if match else CUSTOM
                    st.session_state[f"slot_hex_{i}"] = p.hex
                for i in range(len(cov) - 1):
                    st.session_state[f"cov_pct_{i}"] = round(cov[i] * 100, 1)
                st.session_state["cov_n"] = len(cov)
                st.session_state["_loaded_g"] = sel
                book.selected = sel
                st.rerun()
            book.selected = sel

            st.divider()
            if st_canvas is None:
                st.info("Install `streamlit-drawable-canvas` to draw regions.")
            elif not draw_mode:
                if st.button("➕ Draw a new region"):
                    st.session_state["draw_mode"] = True
                    st.rerun()
            else:
                st.markdown("**New region** — lasso on the image, left.")
                new_name = st.text_input("Region name", value=f"Region {len(book.drawn) + 1}")
                c_add, c_cancel = st.columns(2)
                if c_add.button("Add region", type="primary"):
                    objs = (canvas.json_data or {}).get("objects", []) if canvas else []
                    if not objs:
                        st.warning("Trace a lasso around an area on the image first.")
                    else:
                        sx, sy = src_w / disp_w, src_h / disp_h
                        rings = [scale_points(geometry.points_from_object(o), sx, sy) for o in objs]
                        rmask = polygons_to_mask(rings, (src_h, src_w)) & shading.mask
                        if not rmask.any():
                            st.warning("Lasso didn't overlap the mini — trace around a part of the model.")
                        else:
                            book.add(rmask, new_name.strip() or f"Region {len(book.drawn) + 1}",
                                     default_ramp(st.session_state["n"]),
                                     [c / 100 for c in helpers.current_cov_seed(st.session_state["n"])])
                            st.session_state.pop("_loaded_g", None)
                            for _k in [k for k in list(st.session_state) if k.startswith("rename_")]:
                                st.session_state.pop(_k, None)
                            st.session_state["draw_mode"] = False
                            st.rerun()
                if c_cancel.button("Cancel"):
                    st.session_state["draw_mode"] = False
                    st.rerun()

            if sel >= 1 and st.button("🗑 Delete this region"):
                book.remove(sel)
                st.session_state.pop("_loaded_g", None)
                for _k in [k for k in list(st.session_state) if k.startswith("rename_")]:
                    st.session_state.pop(_k, None)
                st.rerun()

        st.divider()
        st.markdown(f"### Editing: **{book.names()[sel]}**")

        # Rename the selected drawn region (Whole mini / index 0 is fixed).
        if sel >= 1:
            renamed = st.text_input("Region name", value=book.names()[sel], key=f"rename_{sel}")
            if renamed.strip() and renamed.strip() != book.names()[sel]:
                book.set_name_at(sel, renamed)
                st.session_state.pop("_loaded_g", None)
                st.rerun()

        # --- Rehydrate editor widgets from the book (the source of truth) ---
        # Streamlit garbage-collects widget-state keys that weren't rendered during
        # a run. A button that reruns before these editor widgets render (draw-mode
        # toggle, delete, recipe load, add/cancel) drops n / slot_* / cov_pct_*,
        # after which they'd silently reappear at defaults and the write-back would
        # corrupt the region. setdefault restores only the *missing* keys from the
        # selected region, so live user edits (present keys) are untouched.
        _pal = book.palette_at(sel)
        _cov = book.coverage_at(sel)
        st.session_state.setdefault("n", len(_pal))
        for i, p in enumerate(_pal):
            _has_code = bool(p.code) and find_by_code(CATALOG, p.code) is not None
            st.session_state.setdefault(f"slot_code_{i}", p.code if _has_code else CUSTOM)
            st.session_state.setdefault(f"slot_hex_{i}", p.hex)
        for i in range(len(_cov) - 1):
            st.session_state.setdefault(f"cov_pct_{i}", round(_cov[i] * 100, 1))
        st.session_state.setdefault("cov_n", len(_cov))

        # --- recipe loader ---
        recipes = load_all()
        recipe_by_name = {r.name: r for r in recipes}
        name_counts = Counter(p.name for p in CATALOG)
        choice = st.selectbox("Recipe", ["(none)"] + list(recipe_by_name))
        if st.button("Load") and choice != "(none)":
            pal = to_palette(recipe_by_name[choice])
            st.session_state["n"] = max(3, min(5, len(pal)))
            for i, p in enumerate(pal[:st.session_state["n"]]):
                match = find_by_name(CATALOG, p.name)
                unique = name_counts.get(p.name) == 1
                st.session_state[f"slot_code_{i}"] = match.code if (match and unique) else CUSTOM
                st.session_state[f"slot_hex_{i}"] = p.hex
            st.rerun()

        # --- Palette slots (dark to light) ---
        # Seed "n" before the slider widget is created so the widget can own the value via key=
        # without a conflicting value= argument causing a session_state warning.
        st.session_state.setdefault("n", 5)
        n = st.slider("Number of layers", 3, 7, key="n")
        st.markdown("**Palette** (dark to light)")
        palette = []
        options = CATALOG_CODES + [CUSTOM]
        for i in range(n):
            if i < len(DEFAULT_PALETTE):
                default = DEFAULT_PALETTE[i]
            else:
                default = PaintColor(f"Grey {i + 1}", ramp_hex(i, n))
            st.session_state.setdefault(f"slot_code_{i}", default.code)
            st.session_state.setdefault(f"slot_hex_{i}", default.hex)
            default_code = st.session_state[f"slot_code_{i}"]
            if default_code != CUSTOM and find_by_code(CATALOG, default_code) is None:
                default_code = CUSTOM
            c1, c2, c3 = st.columns([3, 1, 1])
            slot_sel = c1.selectbox(
                f"Layer {i + 1}", options,
                index=options.index(default_code),
                format_func=lambda c: CUSTOM if c == CUSTOM else CODE_LABEL.get(c, c),
                key=f"slot_code_{i}",
            )
            if slot_sel == CUSTOM:
                hexv = c2.color_picker(
                    f"hex {i + 1}", key=f"slot_hex_{i}", label_visibility="collapsed",
                )
                pasted = c3.text_input(
                    f"paste hex {i + 1}", value=hexv, key=f"slot_hexinput_{i}",
                    on_change=_apply_paste_hex, args=(i,), label_visibility="collapsed",
                )
                if pasted and valid_hex(pasted) is None:
                    c3.caption("⚠️ invalid hex")
                paint = PaintColor(f"Custom {i + 1}", hexv)
                palette.append(paint)
                near = collection.nearest_paint(paint.rgb, CATALOG)
                if near is not None:
                    owned_badge = "✅ owned" if near.code in set(picked) else "⚠️ not owned"
                    c3.caption(f"{hexv} · closest: {near.name} · {near.code} ({owned_badge})")
            else:
                paint = find_by_code(CATALOG, slot_sel)
                c2.markdown(helpers.swatch(paint.hex, size="2.2em"), unsafe_allow_html=True)
                palette.append(paint)
                st.session_state[f"slot_hex_{i}"] = paint.hex
                badge = "✅ owned" if paint.code in set(picked) else "⚠️ not owned"
                c3.write(f"{paint.hex} · {badge}")

            # Interior slots can be filled with the Lab-midpoint of their neighbours.
            if 0 < i < n - 1:
                c1.button("↕ blend neighbours", key=f"blend_{i}",
                          on_click=_blend_neighbours, args=(i, n))

        # --- Coverage per layer (remainder model) ---
        st.markdown("**Coverage** (% of the model each layer occupies)")
        roles_now = role_names(n)
        cov_floor = 3.0
        n_ctrl = n - 1  # controllable bands; the lightest band is the auto remainder
        seed = [round(f * 100, 1) for f in default_coverage(n)]

        def _cap_slider(idx: int) -> None:
            # Runs on a slider's change, BEFORE the rerun, on committed state.
            # Cap only the moved slider so the controllable total leaves the
            # remainder band at least `cov_floor`. Touching one widget key inside
            # its own on_change callback is the supported Streamlit pattern and
            # avoids the mid-render read/write feedback loop.
            key = f"cov_pct_{idx}"
            others = [st.session_state[f"cov_pct_{j}"]
                      for j in range(n_ctrl) if j != idx]
            smax = slider_max_pct(others, floor=cov_floor)
            if st.session_state[key] > smax:
                st.session_state[key] = smax

        # Seed once (fresh session) and reseed when the layer count changes.
        if st.session_state.get("cov_n") != n:
            for i in range(n_ctrl):
                st.session_state[f"cov_pct_{i}"] = seed[i]
            st.session_state["cov_n"] = n

        if st.button("Reset to default curve"):
            for i in range(n_ctrl):
                st.session_state[f"cov_pct_{i}"] = seed[i]
            st.rerun()

        cov_pcts: list[float] = []
        for i in range(n_ctrl):
            val = st.slider(
                f"{roles_now[i]}", 0.0, 100.0, step=0.5,
                key=f"cov_pct_{i}", on_change=_cap_slider, args=(i,),
            )
            cov_pcts.append(val)

        remainder = remainder_pct(cov_pcts)
        st.caption(f"**{roles_now[-1]} · auto: {remainder:.1f}%**  (remainder — always keeps ≥ {cov_floor:.0f}%)")

        coverage = [p / 100.0 for p in (cov_pcts + [remainder])]  # fractions, sum == 1.0

        # --- Save current palette as a recipe ---
        with st.expander("Save as recipe"):
            rname = st.text_input("Recipe name", key="save_name")
            if st.button("Save recipe") and rname.strip():
                steps = [RecipeStep(label=r, hex=p.hex, paint_ref=(p.name if p.code else None))
                         for r, p in zip(role_names(n), palette)]
                save_user(Recipe(rname.strip(), steps))
                st.success(f"Saved recipe '{rname.strip()}'.")

        # Write the edited palette/coverage back into the book for the selected region.
        book.set_palette_at(sel, palette)
        book.set_coverage_at(sel, coverage)

        # --- Match to my paints (scoped to this region's palette) ---
        st.markdown("#### Match to my paints")
        match_targets = [target_from_paint(p) for p in palette]
        match_roles = role_names(len(palette))
        adhoc = st.color_picker("Ad-hoc colour", value="#808080", key="adhoc_hex")
        if st.checkbox("Include ad-hoc colour", key="adhoc_on"):
            match_targets = match_targets + [target_from_hex(adhoc)]
            match_roles = match_roles + ["Ad-hoc"]
        if not owned_paints:
            st.info("Tick the paints you own (Paints tab) to get match suggestions.")
        else:
            for row in advise(match_targets, match_roles, owned_paints, CATALOG):
                r = row.result
                chips = "".join(helpers.swatch(p.hex) for p in r.paints)
                st.markdown(f"{chips} **{row.role}** — {r.phrase}", unsafe_allow_html=True)
                if row.note:
                    st.caption(row.note)

        st.divider()
        st.markdown("**Edge highlights**")
        edges = st.checkbox("Edge highlights", value=True, key="edge_hl")
        extreme_edge = st.checkbox("Extreme edge highlight", value=False,
                                   key="edge_extreme", disabled=not edges)
        edge_sensitivity = st.slider("Edge sensitivity", 0.0, 1.0, 0.5, 0.05,
                                     key="edge_sens", disabled=not edges,
                                     help="Few sharpest edges (left) to more edges (right).")

        relief_cap = st.checkbox(
            "Auto-reduce bands on flat regions", value=True, key="relief_cap",
            help="A flat region can't show every highlight band — cap it to what the "
                 "relief supports. Untick to force your full band count everywhere.")

        per_region_norm = st.checkbox(
            "Colored / painted mini (experimental)", value=False, key="per_region_norm",
            help="Normalize brightness per region so each painted colour reads its own "
                 "relief. Off = primed-mini mode (default). Needs one lassoed region per "
                 "material; very dark regions may be flagged as too low-contrast to read.")

        # --- Photo quality panel (non-blocking) ---
        # `shading.mask` is the mask computed (and cached) by `helpers.shading()` above —
        # it is the same mask by value that `analyze_regions` will use; reusing it here
        # adds no extra depth-model run.
        try:
            st.subheader("\U0001F4F7 Photo quality")
            for r in check_input(rgb, shading.mask):
                line = f"**{r.label}** — {r.detail}"
                (st.success if r.ok else st.warning)(line)
            st.caption(PAINTED_CAPTURE_NOTE)
            with st.expander("How to photograph your mini"):
                st.markdown(SHOOTING_GUIDE)
        except Exception:
            st.caption("Photo-quality check unavailable for this image.")

        st.divider()
        wp, wcov, drawn = book.analyze_args()
        multi = analyze_regions(rgb, alpha, wp, wcov, drawn,
                                edges=edges, extreme_edge=extreme_edge,
                                edge_sensitivity=edge_sensitivity,
                                relief_cap=relief_cap,
                                per_region_norm=per_region_norm)
        st.image(multi.combined_rgb, caption="Combined painted preview (all regions)",
                 use_container_width=True)
        st.subheader("Colour schemes — all regions")
        st.image(swatch_board([(p.name, p.colors) for p in multi.plans]))
        st.subheader("Paint-along steps by region")
        st.caption("Work dark to light within each region.")
        for plan in multi.plans:
            st.markdown(f"### {plan.name}")
            if plan.flat_albedo:
                st.warning(
                    f"“{plan.name}” is too dark / low-contrast to read relief — showing "
                    f"1 band. Try a paler basecoat here, or a stronger raking side light. "
                    f"(Single-photo tools can’t recover form from a dark, flat colour.)")
            elif plan.capped:
                st.warning(
                    f"“{plan.name}” looks fairly flat — showing {len(plan.names)} "
                    f"band(s) instead of {plan.requested_bands}. Untick "
                    f"“Auto-reduce bands on flat regions” to force all "
                    f"{plan.requested_bands}.")
            helpers.render_region_steps(plan.steps, plan.roles, plan.names, plan.coverage)
    except Exception as e:
        st.error("Error processing image — see traceback below.")
        st.exception(e)
