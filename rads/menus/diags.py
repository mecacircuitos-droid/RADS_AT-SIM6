from __future__ import annotations

"""DIAGS menu.

This module re-creates the RADS-AT *DIAG* navigation shown in the provided
flow chart (LIMITS → Diagnostics warnings → Diagnostic Menu → Corrections,
etc.). The math is didactic and leverages the existing BHT-412-MM rule engine
in `rads.models.diagnosis`.

The LCD shows the original-style pages; long lists are paginated with LEFT/
RIGHT. The softkey labels (MEASURE/DISPLAY/DIAGS/MANAGER) are shown on the
LCD footer bar.
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

from rads.core import Key, LCD, RADSState, Screen
from rads.models.diagnosis import step_detail_for_bht412, step_summaries_for_bht412
from rads.ui.lcd_helpers import header_scientific_atlanta, softkey_bar_html


# -----------------
# Config helpers
# -----------------


_CFG: Dict[str, object] | None = None


def _load_cfg() -> Dict[str, object]:
    global _CFG
    if _CFG is not None:
        return _CFG
    cfg_path = Path(__file__).resolve().parents[1] / "config" / "bht412_mm.json"
    _CFG = json.loads(cfg_path.read_text(encoding="utf-8"))
    return _CFG


def _pick_state(runs: Dict[str, dict], names: List[str]) -> dict:
    for n in names:
        if n in runs:
            return runs[n] or {}
    return {}


def _active_runs(sim: RADSState) -> Tuple[str, Dict[str, dict]]:
    if sim.flight_id and sim.flight_id in sim.measurements:
        return sim.flight_id, sim.measurements.get(sim.flight_id, {}) or {}
    if sim.measurements:
        fid = sorted(sim.measurements.keys())[-1]
        return fid, sim.measurements.get(fid, {}) or {}
    return "", {}


def _global_tab_keys(sim: RADSState, key: Key) -> bool:
    if key == Key.F1:
        sim.push("measure"); sim.menu_index = 0; return True
    if key == Key.F2:
        sim.push("display"); sim.menu_index = 0; return True
    if key == Key.F4:
        sim.push("manager"); sim.menu_index = 0; return True
    return False


def _lcd(sim: RADSState, lines: List[str], *, highlight: int | None, help_line: str) -> LCD:
    lines = lines[:8]
    while len(lines) < 8:
        lines.append("".ljust(38))
    lines.append(help_line[:38].ljust(38))
    return LCD(lines=lines, highlight_line=highlight, inv_lines=[8], footer_html=softkey_bar_html(sim))


# -----------------
# Screen registry
# -----------------


def register_diags(sim: RADSState) -> None:
    sim.screens["diags"] = Screen(
        id="diags",
        title="DIAGS",
        help_text="LIMITS / DIAGNOSTICS",
        render=_render_limits,
        handle=_handle_limits,
    )

    sim.screens["diags_all_limits"] = Screen(
        id="diags_all_limits",
        title="DIAGS / ALL LIMITS",
        help_text="ALL LIMITS",
        render=_render_all_limits,
        handle=_handle_all_limits,
    )

    sim.screens["diags_warnings"] = Screen(
        id="diags_warnings",
        title="DIAGS / WARNINGS",
        help_text="DIAGNOSTIC WARNING",
        render=_render_warnings,
        handle=_handle_warnings,
    )

    sim.screens["diags_menu"] = Screen(
        id="diags_menu",
        title="DIAGS / MENU",
        help_text="Diagnostic Menu",
        render=_render_diag_menu,
        handle=_handle_diag_menu,
    )

    sim.screens["diags_corrections"] = Screen(
        id="diags_corrections",
        title="DIAGS / CORRECTIONS",
        help_text="Corrections",
        render=_render_corrections,
        handle=_handle_corrections,
    )

    sim.screens["diags_predictions"] = Screen(
        id="diags_predictions",
        title="DIAGS / PREDICTIONS",
        help_text="Predictions",
        render=_render_predictions,
        handle=_handle_simple_back,
    )

    sim.screens["diags_adjustables"] = Screen(
        id="diags_adjustables",
        title="DIAGS / ADJUSTABLES",
        help_text="Adjustables",
        render=_render_adjustables,
        handle=_handle_simple_back,
    )

    sim.screens["diags_defaults"] = Screen(
        id="diags_defaults",
        title="DIAGS / DEFAULTS",
        help_text="Defaults",
        render=_render_defaults,
        handle=_handle_simple_back,
    )


# -----------------
# LIMITS page (entry)
# -----------------


def _render_limits(sim: RADSState) -> LCD:
    fid, runs = _active_runs(sim)

    # Headerless: these pages are data-heavy and need every row.
    lines: List[str] = []
    lines.append("LIMITS"[:38].ljust(38))
    lines.append(f"BHT-412-MM  FLT {fid or '-'}"[:38].ljust(38))

    if not (sim.aircraft_type or "").startswith("412"):
        lines.append("BHT-412-MM only"[:38].ljust(38))
        lines.append("Select Bell 412 in MEASURE"[:38].ljust(38))
        while len(lines) < 8:
            lines.append("".ljust(38))
        help_line = "QUIT Back"
        return _lcd(sim, lines, highlight=None, help_line=help_line)

    if not runs:
        lines.append("No measurements yet."[:38].ljust(38))
        lines.append("Run MEASURE first."[:38].ljust(38))
        while len(lines) < 8:
            lines.append("".ljust(38))
        help_line = "QUIT Back"
        return _lcd(sim, lines, highlight=None, help_line=help_line)

    steps = step_summaries_for_bht412(runs)
    all_done = all(s.status == "DONE" for s in steps)
    any_needs = any(s.status == "NEEDS" for s in steps)

    lines.append("".ljust(38))
    if all_done:
        lines.append("Measurements within limits"[:38].ljust(38))
    elif any_needs:
        lines.append("Measurements exceed limits"[:38].ljust(38))
        lines.append("Review DIAGNOSTICS"[:38].ljust(38))
    else:
        lines.append("Incomplete: steps missing"[:38].ljust(38))

    lines.append("".ljust(38))
    lines.append("DO: Warnings   UP: All Limits"[:38].ljust(38))

    while len(lines) < 8:
        lines.append("".ljust(38))

    help_line = "UP All  DO Diag  QUIT Back"
    return _lcd(sim, lines, highlight=None, help_line=help_line)



def _handle_limits(sim: RADSState, key: Key) -> None:
    if _global_tab_keys(sim, key):
        return

    if key == Key.UP:
        sim.diags_page = 0
        sim.push("diags_all_limits")
        return

    if key == Key.DO:
        sim.diags_page = 0
        sim.push("diags_warnings")
        return

    if key == Key.QUIT:
        sim.diags_page = 0
        sim.menu_index = 0
        sim.pop()


# -----------------
# ALL LIMITS
# -----------------


def _limits_entries(sim: RADSState) -> List[Tuple[str, str, str]]:
    """Return list of (item, limit, measured) lines."""
    cfg = _load_cfg()
    fid, runs = _active_runs(sim)
    state_map = cfg.get("state_map", {}) or {}

    out: List[Tuple[str, str, str]] = []

    # Track (60% NR / IDLE)
    tr = _pick_state(runs, list(state_map.get("track60", [])))
    if tr:
        track = tr.get("track_rel_mm", {}) or {}
        h_in = {k: float(track.get(k, 0)) / 25.4 for k in ("RED", "BLU", "ORG", "GRN")}
        rb = h_in["RED"] - h_in["BLU"]
        og = h_in["ORG"] - h_in["GRN"]
        sep = ((h_in["RED"] + h_in["BLU"]) / 2.0) - ((h_in["ORG"] + h_in["GRN"]) / 2.0)
        out.append(("60NR RB diff", f"<= {cfg['track_pair_tol_in']:.2f}in", f"{abs(rb):.2f}in"))
        out.append(("60NR OG diff", f"<= {cfg['track_pair_tol_in']:.2f}in", f"{abs(og):.2f}in"))
        out.append(("60NR Pair sep", f"{cfg['pair_separation_in']:.2f}±{cfg['sep_tol_in']:.2f}", f"{sep:.2f}in"))
    else:
        out.append(("60NR Track", "--", "(missing)"))

    def _vib_line(label: str, m: dict, amp_key: str, ph_key: str, lim: float) -> Tuple[str, str, str]:
        if not m:
            return (label, f"< {lim:.2f}", "(missing)")
        amp = float(m.get(amp_key, 0.0) or 0.0)
        ph = float(m.get(ph_key, 0.0) or 0.0)
        return (label, f"< {lim:.2f}", f"{amp:.3f}@{ph:>3.0f}°")

    gnd = _pick_state(runs, list(state_map.get("ground100", [])))
    out.append(_vib_line("100NR LAT1R", gnd, "lat_1r_ips", "lat_1r_phase_deg", float(cfg["ground_ips_limit"])))

    hov = _pick_state(runs, list(state_map.get("hover", [])))
    out.append(_vib_line("HOVER LAT1R", hov, "lat_1r_ips", "lat_1r_phase_deg", float(cfg["hover_ips_limit"])))

    k120 = _pick_state(runs, list(state_map.get("kias120", [])))
    out.append(_vib_line("120K VRT1R", k120, "vert_1r_ips", "vert_1r_phase_deg", float(cfg["kias120_vert_limit"])))

    ldn = _pick_state(runs, list(state_map.get("letdown", [])))
    out.append(_vib_line("LDN  LAT1R", ldn, "lat_1r_ips", "lat_1r_phase_deg", float(cfg["letdown_ips_limit"])))

    return out


def _render_all_limits(sim: RADSState) -> LCD:
    fid, _ = _active_runs(sim)

    entries = _limits_entries(sim)
    per_page = 6
    pages = max(1, math.ceil(len(entries) / per_page))
    sim.diags_page = max(0, min(sim.diags_page, pages - 1))
    start = sim.diags_page * per_page
    chunk = entries[start:start + per_page]

    lines: List[str] = []
    lines.append(f"ALL LIMITS  FLT {fid or '-'}  {sim.diags_page+1}/{pages}"[:38].ljust(38))
    lines.append("ITEM        LIMIT      MEASURED"[:38].ljust(38))

    for it, lim, meas in chunk:
        ln = f"{it[:12]:<12} {lim[:12]:<12} {meas[:12]:<12}"[:38]
        lines.append(ln.ljust(38))

    while len(lines) < 8:
        lines.append("".ljust(38))

    help_line = "L/R Page  QUIT Back"
    return _lcd(sim, lines, highlight=None, help_line=help_line)


def _handle_all_limits(sim: RADSState, key: Key) -> None:
    if _global_tab_keys(sim, key):
        return

    entries = _limits_entries(sim)
    per_page = 6
    pages = max(1, math.ceil(len(entries) / per_page))

    if key == Key.RIGHT:
        sim.diags_page = (sim.diags_page + 1) % pages
        return
    if key == Key.LEFT:
        sim.diags_page = (sim.diags_page - 1) % pages
        return

    if key == Key.QUIT:
        sim.diags_page = 0
        sim.pop()


# -----------------
# Diagnostic warnings
# -----------------


def _warnings(sim: RADSState) -> List[str]:
    _, runs = _active_runs(sim)
    if not runs:
        return ["No measurements available."]

    steps = step_summaries_for_bht412(runs)
    warn: List[str] = []
    for s in steps:
        if s.status == "NEEDS":
            warn.append(f"{s.label}: OUT OF LIMIT")
        elif s.status in ("MISSING", "LOCKED"):
            warn.append(f"{s.label}: INCOMPLETE")
    if not warn:
        warn.append("All measurements within limits")
    return warn


def _render_warnings(sim: RADSState) -> LCD:
    fid, _ = _active_runs(sim)
    warn = _warnings(sim)

    pages = max(1, len(warn))
    sim.diags_page = max(0, min(sim.diags_page, pages - 1))
    msg = warn[sim.diags_page]

    # Headerless warning page: use the full LCD height so the message is readable.
    lines: List[str] = []
    lines.append(f"FLT {fid or '-'}  PAGE {sim.diags_page+1}/{pages}  Warning"[:38].ljust(38))
    lines.append("Diagnostic Warning"[:38].ljust(38))
    lines.append("".ljust(38))

    # wrap message over up to 5 lines
    s = msg
    for _ in range(5):
        if not s:
            break
        lines.append(s[:38].ljust(38))
        s = s[38:]
    while len(lines) < 8:
        lines.append("".ljust(38))
    lines.append("L/R Page  DOWN Menu  QUIT Back"[:38].ljust(38))

    return LCD(lines=lines[:9], highlight_line=None, inv_lines=[8], footer_html=softkey_bar_html(sim))


def _handle_warnings(sim: RADSState, key: Key) -> None:
    if _global_tab_keys(sim, key):
        return

    warn = _warnings(sim)
    pages = max(1, len(warn))

    if key == Key.RIGHT:
        sim.diags_page = (sim.diags_page + 1) % pages
        return
    if key == Key.LEFT:
        sim.diags_page = (sim.diags_page - 1) % pages
        return

    # Better match the original workflow: use DOWN to open the DIAGS menu.
    if key == Key.DOWN:
        sim.menu_index = 0
        sim.push("diags_menu")
        return

    # QUIT returns to the previous screen (typically Limits).
    if key == Key.QUIT:
        sim.diags_page = 0
        sim.menu_index = 0
        sim.pop()
        return


# -----------------
# Diagnostic menu
# -----------------


_MENU_ITEMS: List[Tuple[str, str]] = [
    ("View Predictions", "diags_predictions"),
    ("Edit Adjustables", "diags_adjustables"),
    ("View Corrections", "diags_corrections"),
    ("Complete Flight", "_complete_flight"),
    ("Summary Display", "_summary"),
    ("View Limits", "diags_all_limits"),
    ("Edit Defaults", "diags_defaults"),
    ("Main Menu", "_main"),
]


def _render_diag_menu(sim: RADSState) -> LCD:
    # Headerless menu so options are readable (matches device screenshots)
    lines: List[str] = []
    lines.append("Diagnostics Menu"[:38].ljust(38))

    idx = sim.menu_index % len(_MENU_ITEMS)

    # 7 items per page + title row = 8 content rows before the help bar
    per_page = 7
    start = (idx // per_page) * per_page
    view = _MENU_ITEMS[start:start + per_page]

    for i, (label, _) in enumerate(view):
        prefix = ">" if (start + i) == idx else " "
        lines.append(f"{prefix}{label}"[:38].ljust(38))

    # pad to 8 rows (title + up to 7 items)
    while len(lines) < 8:
        lines.append("".ljust(38))

    help_line = "UP/DN DO Select  QUIT Back"
    highlight = 1 + (idx - start) if view else None
    return _lcd(sim, lines, highlight=highlight, help_line=help_line)


def _handle_diag_menu(sim: RADSState, key: Key) -> None:
    if _global_tab_keys(sim, key):
        return

    if key in (Key.UP, Key.DOWN):
        sim.menu_index = (sim.menu_index + (1 if key == Key.DOWN else -1)) % len(_MENU_ITEMS)
        return

    if key == Key.DO:
        _, target = _MENU_ITEMS[sim.menu_index % len(_MENU_ITEMS)]
        sim.diags_page = 0
        sim.menu_index = 0

        if target == "_complete_flight":
            # Show an at-a-glance comparison across all recorded regimes.
            sim.display_mode = "COMPLETE_FLIGHT"
            sim.display_page = 0
            sim.menu_index = 0
            sim.push("display_complete_flight")
            return

        if target == "_summary":
            # simplest: reuse DISPLAY menu
            sim.push("display")
            return

        if target == "_main":
            # pop back to root (MEASURE)
            while len(sim.stack) > 1:
                sim.pop()
            sim.menu_index = 0
            return

        sim.push(target)
        return

    if key == Key.QUIT:
        # Back to the previous DIAGS screen (typically warnings).
        sim.diags_page = 0
        sim.menu_index = 0
        sim.pop()


# -----------------
# Corrections
# -----------------


def _hub_weight_table(sim: RADSState) -> Dict[str, int]:
    """Return per-blade hub weights (grams) based on 100NR or HOVER."""
    cfg = _load_cfg()
    _, runs = _active_runs(sim)
    state_map = cfg.get("state_map", {}) or {}

    # Prefer ground 100NR, fall back to hover.
    m = _pick_state(runs, list(state_map.get("ground100", [])))
    if not m:
        m = _pick_state(runs, list(state_map.get("hover", [])))
    if not m:
        return {"BLU": 0, "ORG": 0, "RED": 0, "GRN": 0}

    amp = float(m.get("lat_1r_ips", m.get("vib_1r_ips", 0.0)) or 0.0)
    ph = float(m.get("lat_1r_phase_deg", m.get("vib_1r_phase_deg", 0.0)) or 0.0)
    ips_per_100g = float(cfg.get("hub_weight_sensitivity_ips_per_100g", 0.11) or 0.11)
    grams = int(round((amp / ips_per_100g) * 100.0 / 10.0) * 10.0) if ips_per_100g > 0 else 0

    # correction is 180° from peak
    corr = (ph + 180.0) % 360.0
    blade_az = cfg.get("blade_azimuth_deg", {}) or {}

    # Pick two nearest blades and split.
    def ang_diff(a: float, b: float) -> float:
        d = (a - b) % 360.0
        if d > 180.0:
            d = 360.0 - d
        return abs(d)

    ranked = sorted(((ang_diff(corr, float(az)), blade) for blade, az in blade_az.items()), key=lambda x: x[0])
    chosen = [b for _, b in ranked[:2]] if ranked else ["BLU", "RED"]
    split = int(round(grams / 2.0))
    tbl = {"BLU": 0, "ORG": 0, "RED": 0, "GRN": 0}
    for b in chosen:
        tbl[b] = split
    return tbl


def _render_corrections(sim: RADSState) -> LCD:
    fid, runs = _active_runs(sim)

    # two pages: 0 = hub weights, 1 = step-based text
    page = int(sim.diags_page or 0)
    page = 0 if page < 0 else (1 if page > 1 else page)
    sim.diags_page = page

    lines: List[str] = []
    lines.append(f"CORRECTIONS  FLT {fid or '-'}  {page+1}/2"[:38].ljust(38))

    if page == 0:
        tbl = _hub_weight_table(sim)
        lines.append("Hub Weight (Grams)"[:38].ljust(38))
        lines.append("+ add  - remove"[:38].ljust(38))
        lines.append("-- Blades --"[:38].ljust(38))
        lines.append(f"BLU {tbl['BLU']:+4d}  ORG {tbl['ORG']:+4d}"[:38].ljust(38))
        lines.append(f"RED {tbl['RED']:+4d}  GRN {tbl['GRN']:+4d}"[:38].ljust(38))
        lines.append("".ljust(38))
    else:
        steps = step_summaries_for_bht412(runs)
        need = [s for s in steps if s.status == "NEEDS"]
        if not need:
            lines.append("No corrections required.".ljust(38))
            lines.append("All steps DONE.".ljust(38))
            lines.append("".ljust(38))
            lines.append("".ljust(38))
            lines.append("".ljust(38))
            lines.append("".ljust(38))
        else:
            step = need[0]
            title, detail = step_detail_for_bht412(runs, step.step_id, option_120k=1)
            lines.append(title[:38].ljust(38))
            for ln in detail[:5]:
                lines.append(str(ln)[:38].ljust(38))

    while len(lines) < 8:
        lines.append("".ljust(38))

    help_line = "L/R Page  QUIT Menu"
    return _lcd(sim, lines, highlight=None, help_line=help_line)


def _handle_corrections(sim: RADSState, key: Key) -> None:
    if _global_tab_keys(sim, key):
        return

    if key in (Key.LEFT, Key.RIGHT):
        sim.diags_page = 1 - int(sim.diags_page or 0)
        return

    if key == Key.QUIT:
        sim.diags_page = 0
        sim.menu_index = 0
        sim.push("diags_menu")


# -----------------
# Stubs
# -----------------


def _render_predictions(sim: RADSState) -> LCD:
    fid, runs = _active_runs(sim)
    lines = header_scientific_atlanta(sim, "Predict")
    lines.append(f"FLT {fid or '-'}"[:38].ljust(38))
    lines.append("View Predictions".ljust(38))
    lines.append("(simulator stub)".ljust(38))
    lines.append("".ljust(38))

    # show step statuses as quick context
    if runs:
        steps = step_summaries_for_bht412(runs)
        for s in steps[:3]:
            lines.append(f"{s.label[:28]:<28}{s.status:>8}"[:38].ljust(38))

    help_line = "[QUIT] Back"
    return _lcd(sim, lines, highlight=None, help_line=help_line)


def _render_adjustables(sim: RADSState) -> LCD:
    lines = header_scientific_atlanta(sim, "Adjust")
    lines.append("Edit Adjustables".ljust(38))
    lines.append("(not implemented yet)".ljust(38))
    help_line = "[QUIT] Back"
    return _lcd(sim, lines, highlight=None, help_line=help_line)


def _render_defaults(sim: RADSState) -> LCD:
    lines = header_scientific_atlanta(sim, "Defaults")
    lines.append("Edit Defaults".ljust(38))
    lines.append("(not implemented yet)".ljust(38))
    help_line = "[QUIT] Back"
    return _lcd(sim, lines, highlight=None, help_line=help_line)


def _handle_simple_back(sim: RADSState, key: Key) -> None:
    if _global_tab_keys(sim, key):
        return
    if key == Key.QUIT:
        sim.pop(); sim.menu_index = 0
