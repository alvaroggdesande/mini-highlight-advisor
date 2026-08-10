import os
import tempfile
from collections import Counter

import streamlit as st

from mini_highlight_advisor.catalog import load_catalog, find_by_name, find_by_code
from mini_highlight_advisor import collection
from mini_highlight_advisor.masking import load_image
from mini_highlight_advisor.palette import (
    DEFAULT_PALETTE, PaintColor, role_names, ramp_hex,
    default_coverage, remainder_pct, slider_max_pct,
)
from mini_highlight_advisor.pipeline import prepare_shading, band_and_render
from mini_highlight_advisor.recipes import load_all, to_palette, save_user, Recipe, RecipeStep
from mini_highlight_advisor.advisor import advise
from mini_highlight_advisor.matching import target_from_paint, target_from_hex

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


@st.cache_data(show_spinner=False)
def _shading(image_bytes: bytes, suffix: str):
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name
    try:
        rgb, alpha = load_image(tmp_path)
    finally:
        os.unlink(tmp_path)
    return rgb, alpha, prepare_shading(rgb, alpha)

st.set_page_config(page_title="Mini Highlight Advisor", layout="wide")
st.title("Mini Highlight Advisor")
st.caption(
    "Upload a photo of a primed miniature (background-removed PNG is fastest). "
    "You'll get a painted preview + a paint-by-layer plan. Best on a well-lit, "
    "ideally zenithal-primed model."
)

CATALOG = load_catalog()
CUSTOM = "(custom target)"
CODE_LABEL = {p.code: f"{p.name} · {p.paint_range or ''} · {p.code}" for p in CATALOG}
CATALOG_CODES = [p.code for p in CATALOG]


def _swatch(hexv: str, size: str = "1em") -> str:
    return (
        f"<span style='display:inline-block;width:{size};height:{size};"
        f"background-color:{hexv};border:1px solid #888;"
        f"vertical-align:middle;margin-right:0.5em'></span>"
    )

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
        st.markdown(f"{_swatch(p.hex)}{p.name} · {rng} · {p.code}", unsafe_allow_html=True)

    st.caption(f"Catalogue: {len(CATALOG)} paints (Vallejo Model Color + Game Color)")

# --- 🖌️ Miniature tab: build the plan (unchanged behaviour) ---
with tab_mini:
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
        sel = c1.selectbox(
            f"Layer {i + 1}", options,
            index=options.index(default_code),
            format_func=lambda c: CUSTOM if c == CUSTOM else CODE_LABEL.get(c, c),
            key=f"slot_code_{i}",
        )
        if sel == CUSTOM:
            hexv = c2.color_picker(
                f"hex {i + 1}", key=f"slot_hex_{i}", label_visibility="collapsed",
            )
            paint = PaintColor(f"Custom {i + 1}", hexv)
            palette.append(paint)
            near = collection.nearest_paint(paint.rgb, CATALOG)
            if near is not None:
                owned_badge = "✅ owned" if near.code in set(picked) else "⚠️ not owned"
                c3.caption(f"Closest: {near.name} · {near.paint_range or ''} · {near.code} ({owned_badge})")
        else:
            paint = find_by_code(CATALOG, sel)
            c2.markdown(_swatch(paint.hex, size="2.2em"), unsafe_allow_html=True)
            palette.append(paint)
            c3.write("✅ owned" if paint.code in set(picked) else "⚠️ not owned")

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

    st.divider()
    st.markdown("### Match to my paints")
    st.caption("How to hit each colour with what you own — checked once while you prep.")

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
            chips = "".join(_swatch(p.hex) for p in r.paints)
            st.markdown(f"{chips} **{row.role}** — {r.phrase}", unsafe_allow_html=True)
            if row.note:
                st.caption(row.note)

    uploaded = st.file_uploader("Mini photo", type=["png", "jpg", "jpeg"])
    if uploaded is not None:
        suffix = os.path.splitext(uploaded.name)[1]
        try:
            with st.spinner("Preparing shading (first run downloads the depth model if no alpha channel)..."):
                rgb, alpha, shading = _shading(uploaded.getvalue(), suffix)
            result = band_and_render(rgb, shading.mask, shading.light, palette, coverage)
            st.image(result.panel, caption="Original | Painted preview | Highlight plan", use_container_width=True)
            st.subheader("Layer guide (paint dark to light)")
            for role, paint, cov in zip(result.roles, palette, result.coverage):
                st.markdown(f"**{role}** - {paint.name}  ·  ~{cov:.0f}% of the model")
            st.subheader("Paint-along steps")
            st.caption("Work dark to light. 'Where to paint' = the whole zone for this paint "
                       "(bright marker); 'Apply across' = that same whole zone in the paint colour; "
                       "'Stays this colour' = the smaller slice that remains this colour after you paint "
                       "the lighter layers over the rest.")
            for step, role, paint, cov in zip(result.steps, result.roles, palette, result.coverage):
                cum_cov = sum(result.coverage[step.index:])
                st.markdown(f"**Step {step.index + 1} — {role} · {paint.name}**")
                if step.is_last:
                    c1, c2 = st.columns(2)
                    c1.image(step.zone_rgb, caption="Where to paint", use_container_width=True)
                    c2.image(step.cumulative_rgb, caption=f"Apply across — whole area (~{cum_cov:.0f}%)", use_container_width=True)
                else:
                    c1, c2, c3 = st.columns(3)
                    c1.image(step.zone_rgb, caption="Where to paint", use_container_width=True)
                    c2.image(step.cumulative_rgb, caption=f"Apply across — whole area (~{cum_cov:.0f}%)", use_container_width=True)
                    c3.image(step.exact_rgb, caption=f"Stays this colour — final (~{cov:.0f}%)", use_container_width=True)
        except Exception as e:
            st.error("Error processing image — see traceback below.")
            st.exception(e)
