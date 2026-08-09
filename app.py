import os
import tempfile

import streamlit as st

from mini_highlight_advisor.catalog import load_catalog, find_by_name
from mini_highlight_advisor.collection import annotate_ownership
from mini_highlight_advisor import collection
from mini_highlight_advisor.masking import load_image
from mini_highlight_advisor.palette import DEFAULT_PALETTE, PaintColor, role_names
from mini_highlight_advisor.pipeline import analyze
from mini_highlight_advisor.recipes import load_all, to_palette, save_user, Recipe, RecipeStep

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

st.set_page_config(page_title="Mini Highlight Advisor", layout="wide")
st.title("Mini Highlight Advisor")
st.caption(
    "Upload a photo of a primed miniature (background-removed PNG is fastest). "
    "You'll get a painted preview + a paint-by-layer plan. Best on a well-lit, "
    "ideally zenithal-primed model."
)

CATALOG = load_catalog()
CATALOG_NAMES = [p.name for p in CATALOG]
CUSTOM = "(custom target)"

# --- Sidebar: My paints (owned collection) ---
st.sidebar.markdown("**My paints** (Vallejo)")
owned_names = collection.load()
picked = st.sidebar.multiselect(
    "Paints you own", CATALOG_NAMES, default=sorted(owned_names & set(CATALOG_NAMES)),
    key="owned",
)
if set(picked) != owned_names:
    collection.save(set(picked))
owned_paints = [find_by_name(CATALOG, name) for name in picked]

# --- Main: recipe loader ---
recipes = load_all()
recipe_by_name = {r.name: r for r in recipes}
choice = st.selectbox("Recipe", ["(none)"] + list(recipe_by_name))
if st.button("Load") and choice != "(none)":
    pal = to_palette(recipe_by_name[choice])
    st.session_state["n"] = len(pal)
    for i, p in enumerate(pal):
        st.session_state[f"slot_name_{i}"] = p.name if p.name in CATALOG_NAMES else CUSTOM
        st.session_state[f"slot_hex_{i}"] = p.hex
    st.rerun()

# --- Palette slots (dark to light) ---
# Seed "n" before the slider widget is created so the widget can own the value via key=
# without a conflicting value= argument causing a session_state warning.
st.session_state.setdefault("n", 5)
n = st.slider("Number of layers", 3, 5, key="n")
st.markdown("**Palette** (dark to light)")
palette = []
for i in range(n):
    default = DEFAULT_PALETTE[min(i, len(DEFAULT_PALETTE) - 1)]
    # Seed slot keys before the widgets that own them are created.
    st.session_state.setdefault(f"slot_name_{i}", default.name)
    st.session_state.setdefault(f"slot_hex_{i}", default.hex)
    default_name = st.session_state[f"slot_name_{i}"]
    if default_name not in CATALOG_NAMES:
        default_name = CUSTOM
    c1, c2, c3 = st.columns([3, 1, 1])
    sel = c1.selectbox(
        f"Layer {i + 1}", CATALOG_NAMES + [CUSTOM],
        index=(CATALOG_NAMES + [CUSTOM]).index(default_name), key=f"slot_name_{i}",
    )
    if sel == CUSTOM:
        hexv = c2.color_picker(
            f"hex {i + 1}", key=f"slot_hex_{i}", label_visibility="collapsed",
        )
        palette.append(PaintColor(f"Custom {i + 1}", hexv))
    else:
        paint = find_by_name(CATALOG, sel)
        c2.color_picker(f"hex {i + 1}", value=paint.hex, key=f"view_hex_{i}",
                        disabled=True, label_visibility="collapsed")
        palette.append(paint)
    # owned badge for this slot
    status = annotate_ownership([palette[-1]], owned_paints)[0]
    c3.write("✅ owned" if status.owned else "⚠️ not owned")

# --- Save current palette as a recipe ---
with st.expander("Save as recipe"):
    rname = st.text_input("Recipe name", key="save_name")
    if st.button("Save recipe") and rname.strip():
        steps = [RecipeStep(label=r, hex=p.hex, paint_ref=(p.name if p.name in CATALOG_NAMES else None))
                 for r, p in zip(role_names(n), palette)]
        save_user(Recipe(rname.strip(), steps))
        st.success(f"Saved recipe '{rname.strip()}'.")

uploaded = st.file_uploader("Mini photo", type=["png", "jpg", "jpeg"])
if uploaded is not None:
    suffix = os.path.splitext(uploaded.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getbuffer())
        tmp_path = tmp.name
    try:
        with st.spinner("Analyzing (first run downloads the depth model if no alpha channel)..."):
            rgb, alpha = load_image(tmp_path)
            result = analyze(rgb, alpha, palette)
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
    finally:
        os.unlink(tmp_path)
