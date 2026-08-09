import os
import tempfile

import streamlit as st

from mini_highlight_advisor.masking import load_image
from mini_highlight_advisor.palette import DEFAULT_PALETTE, PaintColor
from mini_highlight_advisor.pipeline import analyze

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

st.set_page_config(page_title="Mini Highlight Advisor", layout="wide")
st.title("Mini Highlight Advisor")
st.caption(
    "Upload a photo of a primed miniature (background-removed PNG is fastest). "
    "You'll get a painted preview + a paint-by-layer plan. Best on a well-lit, "
    "ideally zenithal-primed model."
)

n = st.sidebar.slider("Number of layers", 3, 5, 5)
st.sidebar.markdown("**Palette** (dark to light)")
palette = []
for i in range(n):
    default = DEFAULT_PALETTE[min(i, len(DEFAULT_PALETTE) - 1)]
    c1, c2 = st.sidebar.columns([2, 1])
    name = c1.text_input(f"Layer {i + 1} name", value=default.name, key=f"name{i}")
    hexv = c2.color_picker(f"Layer {i + 1}", value=default.hex, key=f"hex{i}")
    palette.append(PaintColor(name, hexv))

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
