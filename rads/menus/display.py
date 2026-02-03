from __future__ import annotations

"""DISPLAY menu.

Goal: mimic the original RADS-AT flow (figure 3-20A/B) but keeping the
simulator lightweight.

Implementation notes
--------------------
- The *plots* (track bar + vib polar) are rendered **inside** the 38x9 LCD
  content area as ASCII art (closer to the original look and avoids external
  charts under the LCD).
- Navigation matches the rest of the simulator:
    UP/DN = move
    DO    = select
    QUIT  = back
    F1..F4 = jump to top tabs
"""

import math
from typing import Dict, List, Tuple

from rads.core import Key, LCD, RADSState, Screen
from rads.ui.lcd_helpers import header_scientific_atlanta, softkey_bar_html
from rads.models.simulate import plan_sequences_for_412


# -----------------
# Screen registry
# -----------------


def register_display(sim: RADSState) -> None:
    sim.screens["display"] = Screen(
        id="display",
        title="DISPLAY",
        help_text="DISPLAY MODE",
        render=_render_mode,
        handle=_handle_mode,
    )

    sim.screens["display_test_states"] = Screen(
        id="display_test_states",
        title="DISPLAY / TEST STATES",
        help_text="Choose a test state",
        render=_render_test_states,
        handle=_handle_test_states,
    )

    sim.screens["display_displays"] = Screen(
        id="display_displays",
        title="DISPLAY / DISPLAYS",
        help_text="Choose a display",
        render=_render_displays,
        handle=_handle_displays,
    )

    sim.screens["display_complete_flight"] = Screen(
        id="display_complete_flight",
        title="DISPLAY / COMPLETE",
        help_text="Complete flight comparison",
        render=_render_complete_flight,
        handle=_handle_complete_flight,
    )

    sim.screens["display_plot_track"] = Screen(
        id="display_plot_track",
        title="DISPLAY / TRACK PLOT",
        help_text="Bar chart (rel track)",
        render=_render_plot_track,
        handle=_handle_plot_view,
    )

    sim.screens["display_plot_polar"] = Screen(
        id="display_plot_polar",
        title="DISPLAY / POLAR",
        help_text="Polar plot (vibration)",
        render=_render_plot_polar,
        handle=_handle_plot_view,
    )

    sim.screens["display_table"] = Screen(
        id="display_table",
        title="DISPLAY / TABLE",
        help_text="Numeric table",
        render=_render_table,
        handle=_handle_plot_view,
    )


# -----------------
# Helpers
# -----------------


def _active_runs(sim: RADSState) -> Tuple[str, Dict[str, dict]]:
    """Return (flight_id, runs) for the currently active flight."""
    if sim.flight_id and sim.flight_id in sim.measurements:
        return sim.flight_id, sim.measurements.get(sim.flight_id, {}) or {}
    if sim.measurements:
        fid = sorted(sim.measurements.keys())[-1]
        return fid, sim.measurements.get(fid, {}) or {}
    return "", {}


def _available_states(sim: RADSState) -> List[str]:
    """States list shown in DISPLAY.

    Prefer states that actually exist in the active flight; fall back to
    common Bell-412 training regimes.
    """
    _, runs = _active_runs(sim)
    states = list(runs.keys())
    if states:
        return states
    # fallback list (close to screenshots)
    return ["IDLE", "35%TQ", "HOVER", "60K", "100K", "120K", "130K", "140K", "L/DOWN"]


def _ordered_states(sim: RADSState, runs: Dict[str, dict]) -> List[str]:
    """Stable and training-friendly state ordering."""
    states = list(runs.keys())
    if not states:
        return _available_states(sim)

    # For Bell 412 we try to follow the flight plan script order.
    if (sim.aircraft_type or "").startswith("412"):
        plan = sim.flight_plan or "INITIAL"
        seq = plan_sequences_for_412().get(plan, [])
        ordered: List[str] = []
        for s in seq:
            if s in runs and s not in ordered:
                ordered.append(s)
        # Append any extra recorded states (e.g. repeated or special).
        for s in states:
            if s not in ordered:
                ordered.append(s)
        return ordered

    # Fallback: preserve insertion order (dict order) for consistency.
    return states


def _get_run(sim: RADSState) -> Tuple[str, str, dict]:
    fid, runs = _active_runs(sim)
    if not fid or not runs:
        return "", "", {}

    # Resolve selected state; otherwise last completed; otherwise last in dict.
    state = sim.display_state or sim.last_completed_state
    if state and state in runs:
        return fid, state, runs[state]
    last_state = list(runs.keys())[-1]
    return fid, last_state, runs[last_state]


def _global_tab_keys(sim: RADSState, key: Key) -> bool:
    """Handle F1..F4 top navigation. Return True if consumed."""
    if key == Key.F1:
        sim.push("measure"); sim.menu_index = 0; return True
    if key == Key.F3:
        sim.push("diags"); sim.menu_index = 0; return True
    if key == Key.F4:
        sim.push("manager"); sim.menu_index = 0; return True
    return False


def _lcd(sim: RADSState, lines: List[str], *, highlight: int | None, help_line: str) -> LCD:
    # Put a "help" line right above the softkey bar.
    lines = lines[:8]
    while len(lines) < 8:
        lines.append("".ljust(38))
    lines.append(help_line[:38].ljust(38))
    return LCD(lines=lines, highlight_line=highlight, inv_lines=[8], footer_html=softkey_bar_html(sim))


# -----------------
# DISPLAY MODE
# -----------------


def _render_mode(sim: RADSState) -> LCD:
    lines = header_scientific_atlanta(sim, "DISPLAY")
    lines.append("DISPLAY MODE"[:38].ljust(38))

    items = [
        ("One Test", "ONE_TEST"),
        ("Complete Flight", "COMPLETE_FLIGHT"),
        ("Trend Flights", "TREND"),
        ("View Limits", "LIMITS"),
        ("Summary Displays", "SUMMARY"),
    ]
    per_page = 4
    idx = sim.menu_index % len(items)
    start = (idx // per_page) * per_page
    view = items[start:start + per_page]
    for i, (label, _) in enumerate(view):
        prefix = ">" if (start + i) == idx else " "
        lines.append(f"{prefix}{label}"[:38].ljust(38))

    help_line = "UP/DN Move  [DO] Select  [QUIT] Exit"
    return _lcd(sim, lines, highlight=4 + (idx - start), help_line=help_line)


def _handle_mode(sim: RADSState, key: Key) -> None:
    if _global_tab_keys(sim, key):
        return

    items = ["ONE_TEST", "COMPLETE_FLIGHT", "TREND", "LIMITS", "SUMMARY"]
    if key in (Key.UP, Key.DOWN):
        sim.menu_index = (sim.menu_index + (1 if key == Key.DOWN else -1)) % len(items)
        return

    if key == Key.DO:
        sim.display_mode = items[sim.menu_index % len(items)]
        sim.menu_index = 0
        sim.display_page = 0

        if sim.display_mode == "SUMMARY":
            sim.display_view = "TABLE"
            sim.push("display_table")
            return

        if sim.display_mode == "COMPLETE_FLIGHT":
            # Direct summary/compare view across all recorded regimes.
            sim.push("display_complete_flight")
            return

        # ONE_TEST / TREND / LIMITS -> choose a test state first.
        sim.push("display_test_states")
        return

    if key == Key.QUIT:
        sim.menu_index = 0
        sim.pop()


# -----------------
# COMPLETE FLIGHT (comparison across regimes)
# -----------------


def _render_complete_flight(sim: RADSState) -> LCD:
    fid, runs = _active_runs(sim)
    states = _ordered_states(sim, runs)

    # 38x9 screen - keep it headerless for readability.
    lines: List[str] = []
    atype = (sim.aircraft_type or "-").split("_")[0]
    tail = (sim.tail_number or "-")

    pages_total = 3  # 0=amps, 1=phases, 2=track
    page = int(sim.display_page or 0) % pages_total

    lines.append(f"{atype} {tail:<6}  FLT {fid or '-':<4} COMPLETE"[:38].ljust(38))
    if page == 0:
        lines.append("STATE   LAT1R   VRT1R"[:38].ljust(38))
    elif page == 1:
        lines.append("STATE   LATPH   VRTPH"[:38].ljust(38))
    else:
        lines.append("STATE  BLU   ORG   RED   GRN"[:38].ljust(38))

    if not runs:
        for _ in range(6):
            lines.append("(no saved runs yet)"[:38].ljust(38))
        lines.append("QUIT Back"[:38].ljust(38))
        return LCD(lines=lines[:9], highlight_line=None, inv_lines=[8], footer_html=softkey_bar_html(sim))

    # scroll window
    window_rows = 6
    idx = sim.menu_index % max(1, len(states))
    start = (idx // window_rows) * window_rows
    view = states[start:start + window_rows]

    def _mm_to_in(v) -> float:
        try:
            return float(v) / 25.4
        except Exception:
            return 0.0

    for st in view:
        r = runs.get(st, {}) or {}

        if page == 0:
            lat = float(r.get("lat_1r_ips", r.get("vib_1r_ips", 0.0)) or 0.0)
            ver = float(r.get("vert_1r_ips", 0.0) or 0.0)
            ln = f"{st[:6]:<6} {lat:>6.3f} {ver:>6.3f}"[:38]
        elif page == 1:
            latp = float(r.get("lat_1r_phase_deg", r.get("vib_1r_phase_deg", 0.0)) or 0.0)
            verp = float(r.get("vert_1r_phase_deg", 0.0) or 0.0)
            ln = f"{st[:6]:<6} {latp:>6.0f} {verp:>6.0f}"[:38]
        else:
            tr = (r.get("track_rel_mm", {}) or {})
            blu = _mm_to_in(tr.get("BLU", 0.0))
            org = _mm_to_in(tr.get("ORG", 0.0))
            red = _mm_to_in(tr.get("RED", 0.0))
            grn = _mm_to_in(tr.get("GRN", 0.0))
            ln = f"{st[:6]:<6} {blu:+.2f} {org:+.2f} {red:+.2f} {grn:+.2f}"[:38]

        lines.append(ln.ljust(38))

    # help bar
    while len(lines) < 8:
        lines.append("".ljust(38))
    lines.append("UP/DN Scroll  L/R Page  QUIT Back"[:38].ljust(38))

    highlight = 2 + (idx - start) if view else None
    return LCD(lines=lines[:9], highlight_line=highlight, inv_lines=[8], footer_html=softkey_bar_html(sim))



def _handle_complete_flight(sim: RADSState, key: Key) -> None:
    if _global_tab_keys(sim, key):
        return

    _, runs = _active_runs(sim)
    states = _ordered_states(sim, runs)
    if not states:
        if key == Key.QUIT:
            sim.pop(); sim.menu_index = 0
        return

    if key in (Key.UP, Key.DOWN):
        sim.menu_index = (sim.menu_index + (1 if key == Key.DOWN else -1)) % len(states)
        return

    if key in (Key.LEFT, Key.RIGHT):
        sim.display_page = (int(sim.display_page or 0) + (1 if key == Key.RIGHT else -1)) % 3
        return

    if key == Key.QUIT:
        sim.menu_index = 0
        sim.display_page = 0
        sim.pop()


# -----------------
# TEST STATES
# -----------------


def _render_test_states(sim: RADSState) -> LCD:
    lines = header_scientific_atlanta(sim, "DISPLAY")
    fid, runs = _active_runs(sim)
    lines.append(f"Test States  FLT {fid or '-'}"[:38].ljust(38))

    states = _available_states(sim)
    per_page = 4  # with help bar we can show 4 items at a time
    idx = sim.menu_index % max(1, len(states))
    start = (idx // per_page) * per_page
    view = states[start:start + per_page]
    for i, st_name in enumerate(view):
        prefix = ">" if (start + i) == idx else " "
        lines.append(f"{prefix}{st_name}"[:38].ljust(38))

    if not runs:
        lines.append("(no saved runs yet)"[:38].ljust(38))

    help_line = "UP/DN  [DO] Select  [QUIT] Back"
    return _lcd(sim, lines, highlight=4 + (idx - start), help_line=help_line)


def _handle_test_states(sim: RADSState, key: Key) -> None:
    if _global_tab_keys(sim, key):
        return

    states = _available_states(sim)
    if not states:
        if key == Key.QUIT:
            sim.pop(); sim.menu_index = 0
        return

    if key in (Key.UP, Key.DOWN):
        sim.menu_index = (sim.menu_index + (1 if key == Key.DOWN else -1)) % len(states)
        return

    if key == Key.DO:
        sim.display_state = states[sim.menu_index % len(states)]
        sim.menu_index = 0
        sim.push("display_displays")
        return

    if key == Key.QUIT:
        sim.menu_index = 0
        sim.pop()


# -----------------
# DISPLAYS list
# -----------------


def _render_displays(sim: RADSState) -> LCD:
    lines = header_scientific_atlanta(sim, "DISPLAY")
    fid, state, run = _get_run(sim)
    lines.append(f"DISPLAYS  {state or '-'}"[:38].ljust(38))

    items = [
        ("Rel Track (bar)", "REL_TRACK"),
        ("1R Polar (vib)", "POLAR_1R"),
        ("Table", "TABLE"),
    ]
    idx = sim.menu_index % len(items)
    for i, (label, _) in enumerate(items):
        prefix = ">" if i == idx else " "
        lines.append(f"{prefix}{label}"[:38].ljust(38))

    if not run:
        lines.append("No data for this state"[:38].ljust(38))

    help_line = "UP/DN  [DO] View  [QUIT] Back"
    return _lcd(sim, lines, highlight=4 + idx, help_line=help_line)


def _handle_displays(sim: RADSState, key: Key) -> None:
    if _global_tab_keys(sim, key):
        return

    items = ["REL_TRACK", "POLAR_1R", "TABLE"]

    if key in (Key.UP, Key.DOWN):
        sim.menu_index = (sim.menu_index + (1 if key == Key.DOWN else -1)) % len(items)
        return

    if key == Key.DO:
        sim.display_view = items[sim.menu_index % len(items)]
        # In plot views we use menu_index to highlight the currently selected
        # test state inside the plot/table.
        fid, runs = _active_runs(sim)
        states = _ordered_states(sim, runs)
        if states and sim.display_state in states:
            sim.menu_index = states.index(sim.display_state)
        else:
            sim.menu_index = 0
        if sim.display_view == "REL_TRACK":
            sim.push("display_plot_track")
        elif sim.display_view == "POLAR_1R":
            sim.push("display_plot_polar")
        else:
            sim.push("display_table")
        return

    if key == Key.QUIT:
        sim.menu_index = 0
        sim.pop()


# -----------------
# Plot / table views
# -----------------


def _render_plot_track(sim: RADSState) -> LCD:
    fid, runs = _active_runs(sim)
    states = _ordered_states(sim, runs) if runs else _available_states(sim)
    if not states:
        states = ["-"]

    idx = sim.menu_index % len(states)
    sel = states[idx]
    if runs:
        sim.display_state = sel

    atype = (sim.aircraft_type or "-").split("_")[0]
    tail = (sim.tail_number or "-")

    # Headerless plot view (use full LCD height). Keep a single compact title row
    # so the chart occupies the maximum space.
    lines: List[str] = []
    lines.append(f"{atype} {tail:<6} TRACK MAIN REL. TO MEAN"[:38].ljust(38))

    # 7 state rows + one blade label row.
    window_rows = 7
    start = (idx // window_rows) * window_rows
    view = states[start:start + window_rows]

    def _cell(v_in: float | None, scale_in: float = 1.0) -> str:
        if v_in is None:
            return " " * 7
        # map [-scale..+scale] into 0..6 with 3 as center
        pos = int(round((v_in / scale_in) * 3.0)) + 3
        pos = 0 if pos < 0 else (6 if pos > 6 else pos)
        base = list("   |   ")
        base[pos] = "*"
        return "".join(base)

    def _mm_to_in(x) -> float:
        try:
            return float(x) / 25.4
        except Exception:
            return 0.0

    for st_name in view:
        run = (runs.get(st_name, {}) or {}) if runs else {}
        tr = run.get("track_rel_mm", {}) or {}

        blu = _mm_to_in(tr.get("BLU", 0.0)) if run else None
        org = _mm_to_in(tr.get("ORG", 0.0)) if run else None
        red = _mm_to_in(tr.get("RED", 0.0)) if run else None
        grn = _mm_to_in(tr.get("GRN", 0.0)) if run else None

        ln = (
            f"{st_name[:6]:<6} "
            + _cell(blu) + " "
            + _cell(org) + " "
            + _cell(red) + " "
            + _cell(grn)
        )
        lines.append(ln[:38].ljust(38))

    # Fill missing state rows (if we have fewer recorded states)
    while len(lines) < 1 + window_rows:
        lines.append("".ljust(38))

    # Blade labels line aligned under the 7-char mini-axes
    def _lbl7(s: str) -> str:
        return s[:7].center(7)

    lines.append(
        (" " * 7)
        + _lbl7("BLU") + " "
        + _lbl7("ORG") + " "
        + _lbl7("RED") + " "
        + _lbl7("GRN")
    )

    # Highlight the selected state row (like the original black bar)
    highlight = 1 + (idx - start) if view else None
    return LCD(lines=lines[:9], highlight_line=highlight, inv_lines=[], footer_html=softkey_bar_html(sim))


def _render_plot_polar(sim: RADSState) -> LCD:
    fid, runs = _active_runs(sim)
    states = _ordered_states(sim, runs) if runs else _available_states(sim)
    if not states:
        states = ["-"]

    idx = sim.menu_index % len(states)
    sel = states[idx]
    if runs:
        sim.display_state = sel

    run = (runs.get(sel, {}) or {}) if runs else {}
    amp = float(run.get("lat_1r_ips", run.get("vib_1r_ips", 0.0)) or 0.0)
    ph = float(run.get("lat_1r_phase_deg", run.get("vib_1r_phase_deg", 0.0)) or 0.0)

    # Split LCD into left table + right polar plot.
    LW = 19
    RW = 19

    atype = (sim.aircraft_type or "-").split("_")[0]
    tail = (sim.tail_number or "-")

    # Choose a sensible scale so the vector reaches the outer ring near limit.
    limit = max(0.30, amp, 0.01)

    def _polar_canvas(w: int, h: int, a: float, deg: float, lim: float) -> List[str]:
        cx = w // 2
        cy = h // 2
        r = min(cx, cy) - 1
        grid = [[" " for _ in range(w)] for _ in range(h)]

        # rings
        for rr, ch in ((r, "o"), (max(1, int(round(r * 0.66))), ".")):
            for ang in range(0, 360, 15):
                rad = math.radians(ang)
                x = int(round(cx + rr * math.cos(rad)))
                y = int(round(cy - rr * math.sin(rad)))
                if 0 <= x < w and 0 <= y < h:
                    grid[y][x] = ch

        # crosshair axes
        for x in range(w):
            if grid[cy][x] == " ":
                grid[cy][x] = "-"
        for y in range(h):
            if grid[y][cx] == " ":
                grid[y][cx] = "|"
        grid[cy][cx] = "+"

        # vector: 0 deg at top, CW positive (RADS-like)
        rad = math.radians(90.0 - (deg % 360.0))
        frac = 0.0 if lim <= 0 else max(0.0, min(1.0, a / lim))
        rr = int(round(frac * r))
        ex = int(round(cx + rr * math.cos(rad)))
        ey = int(round(cy - rr * math.sin(rad)))

        # Bresenham-ish line from center to endpoint
        steps = max(abs(ex - cx), abs(ey - cy), 1)
        for i in range(1, steps + 1):
            x = int(round(cx + (ex - cx) * (i / steps)))
            y = int(round(cy + (ey - cy) * (i / steps)))
            if 0 <= x < w and 0 <= y < h:
                if grid[y][x] in (" ", "-", "|", "."):
                    grid[y][x] = "*"
        if 0 <= ex < w and 0 <= ey < h:
            grid[ey][ex] = "X" if rr > 0 else "+"

        return ["".join(row) for row in grid]

    right = _polar_canvas(RW, 9, amp, ph, limit)

    # Left: list of states + amp/phase
    lines: List[str] = []
    top_left = f"{atype} {tail:<6} FLT {fid or '-'}"[:LW].ljust(LW)
    lines.append((top_left + right[0])[:38].ljust(38))
    lines.append(("STATE  AMP   PH".ljust(LW) + right[1])[:38].ljust(38))

    window_rows = 6
    start = (idx // window_rows) * window_rows
    view = states[start:start + window_rows]

    for r_i, st_name in enumerate(view):
        rrun = (runs.get(st_name, {}) or {}) if runs else {}
        a = float(rrun.get("lat_1r_ips", rrun.get("vib_1r_ips", 0.0)) or 0.0)
        p = float(rrun.get("lat_1r_phase_deg", rrun.get("vib_1r_phase_deg", 0.0)) or 0.0)
        left = f"{st_name[:6]:<6} {a:>5.3f} {p:>4.0f}"[:LW].ljust(LW)
        lines.append((left + right[2 + r_i])[:38].ljust(38))

    # bottom line: show limit used for scaling
    lim_txt = f"LIM {limit:.2f} ips"[:LW].ljust(LW)
    lines.append((lim_txt + right[8])[:38].ljust(38))

    highlight = 2 + (idx - start) if view else None
    return LCD(lines=lines[:9], highlight_line=highlight, inv_lines=[], footer_html=softkey_bar_html(sim))


def _render_table(sim: RADSState) -> LCD:
    lines = header_scientific_atlanta(sim, "Table")
    fid, state, run = _get_run(sim)
    lines.append(f"FLT {fid or '-'}  {state or '-'}"[:38].ljust(38))

    if not run:
        lines.append("No data.".ljust(38))
        help_line = "[QUIT] Back"
        return _lcd(sim, lines, highlight=None, help_line=help_line)

    t = run.get("track_rel_mm", {}) or {}
    lat = float(run.get("lat_1r_ips", run.get("vib_1r_ips", 0.0)) or 0.0)
    latp = float(run.get("lat_1r_phase_deg", run.get("vib_1r_phase_deg", 0.0)) or 0.0)
    ver = float(run.get("vert_1r_ips", 0.0) or 0.0)
    verp = float(run.get("vert_1r_phase_deg", 0.0) or 0.0)

    # Keep table compact for 38x8 area
    lines.append(f"TRK BLU {t.get('BLU','-'):>4}  RED {t.get('RED','-'):>4}"[:38].ljust(38))
    lines.append(f"TRK ORG {t.get('ORG','-'):>4}  GRN {t.get('GRN','-'):>4}"[:38].ljust(38))
    lines.append(f"LAT1R {lat:.3f}@{latp:>3.0f}  VRT1R {ver:.3f}@{verp:>3.0f}"[:38].ljust(38))

    help_line = "[QUIT] Back"
    return _lcd(sim, lines, highlight=None, help_line=help_line)


def _handle_plot_view(sim: RADSState, key: Key) -> None:
    if _global_tab_keys(sim, key):
        return

    # DO toggles to table for the plot screens.
    if key == Key.DO and sim.current.id in ("display_plot_track", "display_plot_polar"):
        sim.push("display_table")
        return

    # In plot views, UP/DN scroll through the available test states.
    if sim.current.id in ("display_plot_track", "display_plot_polar") and key in (Key.UP, Key.DOWN):
        _, runs = _active_runs(sim)
        states = _ordered_states(sim, runs) if runs else _available_states(sim)
        if not states:
            return
        sim.menu_index = (sim.menu_index + (1 if key == Key.DOWN else -1)) % len(states)
        sim.display_state = states[sim.menu_index]
        return

    if key == Key.QUIT:
        # Keep menu_index as state selector while inside plots.
        # If we are leaving the table back to a plot, don't reset.
        if sim.current.id == "display_table":
            sim.pop()
            return
        sim.menu_index = 0
        sim.pop()
