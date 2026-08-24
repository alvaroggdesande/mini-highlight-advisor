"""Global virtual-light control for PS mode: az/el sliders + presets.

Any change re-runs Streamlit; the caller re-derives the plan from (az, el).
"""
import streamlit as st

from ui import keys

PRESETS = {
    "Upper-left": (225, 45),
    "Top": (90, 80),
    "Raking-L": (200, 20),
    "Raking-R": (340, 20),
}


def render() -> tuple[float, float]:
    st.markdown("**Virtual light** — drag to move where the highlights fall.")
    cols = st.columns(len(PRESETS))
    for col, (name, (az, el)) in zip(cols, PRESETS.items()):
        if col.button(name, key=f"preset_{name}"):
            st.session_state[keys.LIGHT_AZ] = az
            st.session_state[keys.LIGHT_EL] = el
            st.rerun()
    az = st.slider("Azimuth °", 0, 360, st.session_state.get(keys.LIGHT_AZ, 225),
                   key=keys.LIGHT_AZ)
    el = st.slider("Elevation °", 0, 90, st.session_state.get(keys.LIGHT_EL, 45),
                   key=keys.LIGHT_EL)
    return float(az), float(el)
