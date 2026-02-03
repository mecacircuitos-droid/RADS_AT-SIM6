from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from rads.core import RADSState
from rads.menus import register_all
from rads.ui import render_device


def _load_css() -> None:
    css_path = Path(__file__).with_name("assets.css")
    st.markdown(css_path.read_text(encoding="utf-8"), unsafe_allow_html=True)


def _init_sim() -> RADSState:
    sim = RADSState()
    register_all(sim)
    return sim


st.set_page_config(page_title="RADS-AT Simulator", layout="wide")
_load_css()

if "sim" not in st.session_state:
    st.session_state.sim = _init_sim()

sim: RADSState = st.session_state.sim

# Sidebar utilities
st.sidebar.header("RADS-AT Simulator")
st.sidebar.caption("Simulation only. No aircraft DB needed.")

if st.sidebar.button("Export session JSON"):
    payload = {
        "aircraft_type": sim.aircraft_type,
        "aircraft_version": sim.aircraft_version,
        "tail_number": sim.tail_number,
        "flight_plan": sim.flight_plan,
        "flight_id": sim.flight_id,
        "measurements": sim.measurements,
    }
    st.sidebar.download_button(
        "Download JSON",
        data=json.dumps(payload, indent=2),
        file_name="rads_session.json",
        mime="application/json",
    )

st.sidebar.markdown("---")
st.sidebar.caption("Use the on-screen keys to navigate.")

render_device(sim)
