import os

import streamlit as st

from mini_highlight_advisor.palette import (
    role_names,
    default_coverage, remainder_pct, slider_max_pct, default_ramp,
)
from mini_highlight_advisor.pipeline import prepare_shading, analyze_regions
from mini_highlight_advisor.advisor import advise
from mini_highlight_advisor.matching import target_from_paint, target_from_hex
from mini_highlight_advisor.regions import Region, scale_points, polygon_to_mask, polygons_to_mask
from mini_highlight_advisor.overlay import swatch_board
from mini_highlight_advisor.region_state import RegionBook, new_book
from mini_highlight_advisor.input_check import check_input, SHOOTING_GUIDE, PAINTED_CAPTURE_NOTE
from ui import context, geometry, helpers, keys, paints_tab, state, palette_editor
from ui.compat import st_canvas
from PIL import Image


st.set_page_config(page_title="Mini Highlight Advisor", layout="wide")
st.title("Mini Highlight Advisor")
st.caption(
    "Upload a photo of a primed miniature (background-removed PNG is fastest). "
    "You'll get a painted preview + a paint-by-layer plan. Best with a raking "
    "side light (not on-axis flash) — that gives the sculpt the shadows the tool reads."
)



tab_mini, tab_paints = st.tabs(["🖌️ Miniature", "🎨 Paints"])

# NOTE: st.tabs runs BOTH bodies every rerun, in code order. Fill the Paints
# tab FIRST so owned_codes / owned_paints are finalised before the Miniature
# tab renders its ownership badges. Display order (Miniature first) is fixed by
# the label list above, not by code order — do not reorder the labels.

# --- 🎨 Paints tab: inventory ---
with tab_paints:
    picked, owned_paints = paints_tab.render()

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
            state.load_region_into_widgets(book, sel)
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
                            st.session_state.pop(keys.LOADED_G, None)
                            for _k in [k for k in list(st.session_state) if k.startswith("rename_")]:
                                st.session_state.pop(_k, None)
                            st.session_state["draw_mode"] = False
                            st.rerun()
                if c_cancel.button("Cancel"):
                    st.session_state["draw_mode"] = False
                    st.rerun()

            if sel >= 1 and st.button("🗑 Delete this region"):
                book.remove(sel)
                st.session_state.pop(keys.LOADED_G, None)
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
                st.session_state.pop(keys.LOADED_G, None)
                st.rerun()

        state.rehydrate_editor_widgets(book, sel)

        palette, n = palette_editor.render(book, sel, picked)

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
        palette_editor.render_save_recipe(palette, n)

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
            for row in advise(match_targets, match_roles, owned_paints, context.CATALOG):
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
