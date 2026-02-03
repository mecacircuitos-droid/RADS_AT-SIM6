from __future__ import annotations

"""Small plot helpers rendered under the LCD.

The original RADS-AT LCD can show simple bar and polar plots. In this
simulator, the LCD itself stays text-only, while plots are rendered beneath it
in the same Streamlit column.
"""

import math
from typing import Dict, Tuple

import streamlit as st


def _active_run(sim) -> Tuple[str, str, Dict[str, object]]:
    """Return (flight_id, state, run_dict)."""
    if getattr(sim, "flight_id", "") and sim.flight_id in getattr(sim, "measurements", {}):
        runs = sim.measurements.get(sim.flight_id, {}) or {}
        fid = sim.flight_id
    else:
        keys = sorted(getattr(sim, "measurements", {}).keys())
        fid = keys[-1] if keys else ""
        runs = sim.measurements.get(fid, {}) if fid else {}
        runs = runs or {}

    if not fid or not runs:
        return "", "", {}

    state = getattr(sim, "display_state", "") or getattr(sim, "last_completed_state", "")
    if state and state in runs:
        return fid, state, runs[state] or {}
    last_state = list(runs.keys())[-1]
    return fid, last_state, runs[last_state] or {}


def render_display_graphics(sim) -> None:
    """Render charts under the LCD when the DISPLAY plot pages are active."""
    sid = getattr(getattr(sim, "current", None), "id", "")
    if sid not in ("display_plot_track", "display_plot_polar"):
        return

    fid, state, run = _active_run(sim)
    if not run:
        return

    # Lazy-import matplotlib so the app still runs if plots are unused.
    import matplotlib.pyplot as plt  # type: ignore

    if sid == "display_plot_track":
        t = run.get("track_rel_mm", {}) or {}
        labels = ["BLU", "ORG", "RED", "GRN"]
        vals = [int(t.get(k, 0) or 0) for k in labels]

        fig = plt.figure(figsize=(5.8, 2.9), dpi=120)
        ax = fig.add_subplot(111)
        ax.bar(labels, vals)
        ax.set_title(f"Rel Track (mm)  FLT {fid}  {state}")
        ax.set_ylabel("mm (rel mean)")
        ax.axhline(0, linewidth=1)
        st.pyplot(fig, use_container_width=True)
        return

    # Polar vibration: show LAT 1R and VRT 1R vectors.
    lat = float(run.get("lat_1r_ips", run.get("vib_1r_ips", 0.0)) or 0.0)
    latp = float(run.get("lat_1r_phase_deg", run.get("vib_1r_phase_deg", 0.0)) or 0.0)
    ver = float(run.get("vert_1r_ips", 0.0) or 0.0)
    verp = float(run.get("vert_1r_phase_deg", 0.0) or 0.0)

    fig = plt.figure(figsize=(5.8, 3.1), dpi=120)
    ax = fig.add_subplot(111, projection="polar")
    ax.set_title(f"1R Polar (ips)  FLT {fid}  {state}")

    def _plot_vec(amp: float, deg: float, label: str) -> None:
        th = math.radians(deg)
        ax.plot([th, th], [0, amp], marker="o", label=label)

    _plot_vec(lat, latp, "LAT 1R")
    _plot_vec(ver, verp, "VRT 1R")
    ax.set_rmax(max(lat, ver, 0.1) * 1.25)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.15))
    st.pyplot(fig, use_container_width=True)
