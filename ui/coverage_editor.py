"""Per-layer coverage sliders (remainder model)."""
import streamlit as st

from mini_highlight_advisor.palette import (
    role_names, default_coverage, remainder_pct, slider_max_pct,
)
from ui import keys

_COV_FLOOR = 3.0


def _cap_slider(idx: int, n_ctrl: int) -> None:
    key = keys.cov_pct(idx)
    others = [st.session_state[keys.cov_pct(j)] for j in range(n_ctrl) if j != idx]
    smax = slider_max_pct(others, floor=_COV_FLOOR)
    if st.session_state[key] > smax:
        st.session_state[key] = smax


def render(n: int, is_nmm: bool = False, sel: int = 0) -> list[float]:
    if is_nmm:
        st.markdown("**Metal steps** (value bands for this NMM region)")
        steps = st.number_input(
            "Metal steps", min_value=2, max_value=n, value=min(5, n), step=1,
            key=keys.metal_steps(sel),
            help="How many brightness bands the reflected environment is cut into. "
                 "NMM has no per-band coverage — each step owns a fixed value range.")
        return default_coverage(int(steps))
    st.markdown("**Coverage** (% of the model each layer occupies)")
    roles_now = role_names(n)
    n_ctrl = n - 1  # controllable bands; lightest band is the auto remainder
    seed = [round(f * 100, 1) for f in default_coverage(n)]

    if st.session_state.get(keys.COV_N) != n:
        for i in range(n_ctrl):
            st.session_state[keys.cov_pct(i)] = seed[i]
        st.session_state[keys.COV_N] = n

    if st.button("Reset to default curve"):
        for i in range(n_ctrl):
            st.session_state[keys.cov_pct(i)] = seed[i]
        st.rerun()

    cov_pcts: list[float] = []
    for i in range(n_ctrl):
        val = st.slider(
            f"{roles_now[i]}", 0.0, 100.0, step=0.5,
            key=keys.cov_pct(i), on_change=_cap_slider, args=(i, n_ctrl),
        )
        cov_pcts.append(val)

    remainder = remainder_pct(cov_pcts)
    st.caption(f"**{roles_now[-1]} · auto: {remainder:.1f}%**  (remainder — always keeps ≥ {_COV_FLOOR:.0f}%)")
    return [p / 100.0 for p in (cov_pcts + [remainder])]  # fractions, sum == 1.0
