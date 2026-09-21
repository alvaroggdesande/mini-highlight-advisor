"""Global virtual-light control for PS mode: az/el sliders + presets.

Any change re-runs Streamlit; the caller re-derives the plan from (az, el).
"""
import streamlit as st

from i18n import t
from ui import keys

def render() -> tuple[float, float]:
    st.markdown(t("relight.heading"))
    _presets = [
        (t("relight.preset_upper_left"), "upper_left", 225, 45),
        (t("relight.preset_top"),        "top",        90,  80),
        (t("relight.preset_raking_l"),   "raking_l",   200, 20),
        (t("relight.preset_raking_r"),   "raking_r",   340, 20),
    ]
    cols = st.columns(len(_presets))
    for col, (label, key_name, az, el) in zip(cols, _presets):
        if col.button(label, key=f"preset_{key_name}"):
            st.session_state[keys.LIGHT_AZ] = az
            st.session_state[keys.LIGHT_EL] = el
            st.rerun()
    az = st.slider(t("relight.azimuth_label"), 0, 360, st.session_state.get(keys.LIGHT_AZ, 225),
                   key=keys.LIGHT_AZ)
    el = st.slider(t("relight.elevation_label"), 0, 90, st.session_state.get(keys.LIGHT_EL, 45),
                   key=keys.LIGHT_EL)
    return float(az), float(el)
