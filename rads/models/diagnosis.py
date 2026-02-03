from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------
# BHT-412-MM sequential decision engine
# ---------------------------------


@dataclass(frozen=True)
class StepSummary:
    step_id: str
    label: str
    status: str  # LOCKED | NEEDS | DONE | MISSING


def step_summaries_for_bht412(runs: Dict[str, dict]) -> List[StepSummary]:
    """Return the 5-step sequential workflow with status tags."""
    cfg = _load_cfg()

    s1 = _status_track60(runs, cfg)
    s2 = _status_ground100(runs, cfg, prev_ok=(s1 == "DONE"))
    s3 = _status_hover(runs, cfg, prev_ok=(s1 == "DONE" and s2 == "DONE"))
    s4 = _status_120k(runs, cfg, prev_ok=(s1 == "DONE" and s2 == "DONE" and s3 == "DONE"))
    s5 = _status_letdown(runs, cfg, prev_ok=(s1 == "DONE" and s2 == "DONE" and s3 == "DONE" and s4 == "DONE"))

    return [
        StepSummary("track60", "GND 60% NR  Track Mech", s1),
        StepSummary("ground100", "GND 100% NR  Mass Bal", s2),
        StepSummary("hover", "HOVER  Lateral Decision", s3),
        StepSummary("kias120", "120 KIAS  Vertical Smooth", s4),
        StepSummary("letdown", "LETDOWN  Final Trim", s5),
    ]


def step_detail_for_bht412(
    runs: Dict[str, dict],
    step_id: str,
    *,
    option_120k: int = 1,
) -> Tuple[str, List[str]]:
    """Return (title, lines) for one step.

    option_120k: user-selected strategy for 120 KIAS
      1 = Bend tab of Blade X UP
      2 = Bend tab of opposite Blade Y DOWN
    """

    cfg = _load_cfg()

    # Evaluate gating first
    summaries = {s.step_id: s.status for s in step_summaries_for_bht412(runs)}
    status = summaries.get(step_id, "MISSING")

    if status in ("LOCKED", "MISSING"):
        title = {
            "track60": "60% NR (Track)",
            "ground100": "100% NR (Ground Bal)",
            "hover": "Hover (Decision)",
            "kias120": "120 KIAS (Vert)",
            "letdown": "Letdown (Trim)",
        }.get(step_id, "DIAGS")

        lines: List[str] = []
        if status == "MISSING":
            lines.append("No measurement for this step.")
            lines.append("Go to MEASURE and run the regime.")
        else:
            lines.append("LOCKED: complete previous steps")
            lines.append("and re-measure until they are DONE.")
        return title, _wrap(lines)

    # Unlocked -> build recommendations
    if step_id == "track60":
        return _detail_track60(runs, cfg)
    if step_id == "ground100":
        return _detail_ground100(runs, cfg)
    if step_id == "hover":
        return _detail_hover(runs, cfg)
    if step_id == "kias120":
        return _detail_120k(runs, cfg, option_120k=option_120k)
    if step_id == "letdown":
        return _detail_letdown(runs, cfg)

    return "DIAGS", ["Unknown step"]


# -----------------
# Status evaluation
# -----------------


def _status_track60(runs: Dict[str, dict], cfg: dict) -> str:
    m = _pick_state(runs, cfg["state_map"]["track60"])
    if not m:
        return "MISSING"
    ok, _ = _track_checks(m, cfg)
    return "DONE" if ok else "NEEDS"


def _status_ground100(runs: Dict[str, dict], cfg: dict, *, prev_ok: bool) -> str:
    if not prev_ok:
        return "LOCKED"
    m = _pick_state(runs, cfg["state_map"]["ground100"])
    if not m:
        return "MISSING"
    amp = float(m.get("lat_1r_ips", m.get("vib_1r_ips", 0.0)) or 0.0)
    return "DONE" if amp < float(cfg["ground_ips_limit"]) else "NEEDS"


def _status_hover(runs: Dict[str, dict], cfg: dict, *, prev_ok: bool) -> str:
    if not prev_ok:
        return "LOCKED"
    m = _pick_state(runs, cfg["state_map"]["hover"])
    if not m:
        return "MISSING"
    amp = float(m.get("lat_1r_ips", m.get("vib_1r_ips", 0.0)) or 0.0)
    return "DONE" if amp < float(cfg["hover_ips_limit"]) else "NEEDS"


def _status_120k(runs: Dict[str, dict], cfg: dict, *, prev_ok: bool) -> str:
    if not prev_ok:
        return "LOCKED"
    m = _pick_state(runs, cfg["state_map"]["kias120"])
    if not m:
        return "MISSING"
    amp = float(m.get("vert_1r_ips", 0.0) or 0.0)
    return "DONE" if amp < float(cfg["kias120_vert_limit"]) else "NEEDS"


def _status_letdown(runs: Dict[str, dict], cfg: dict, *, prev_ok: bool) -> str:
    if not prev_ok:
        return "LOCKED"
    m = _pick_state(runs, cfg["state_map"]["letdown"])
    if not m:
        return "MISSING"
    amp = float(m.get("lat_1r_ips", m.get("vib_1r_ips", 0.0)) or 0.0)
    return "DONE" if amp < float(cfg["letdown_ips_limit"]) else "NEEDS"


# -----------------
# Step details
# -----------------


def _detail_track60(runs: Dict[str, dict], cfg: dict) -> Tuple[str, List[str]]:
    m = _pick_state(runs, cfg["state_map"]["track60"])
    if not m:
        return "60% NR (Track)", ["No 60% NR track measurement."]

    ok, info = _track_checks(m, cfg)
    title = "60% NR - Track Mechanical"

    lines: List[str] = []
    lines.append(f"Status: {'DONE' if ok else 'NEEDS'}")
    lines.append(f"Pair sep: {info['sep_in']:.2f} in (target {cfg['pair_separation_in']:.2f})")
    lines.append(f"RB diff : {info['rb_diff_in']:.2f} in")
    lines.append(f"OG diff : {info['og_diff_in']:.2f} in")

    if ok:
        lines.append("No correction required.")
        return title, _wrap(lines)

    flat_in = float(cfg["pitch_link_flat_in"])
    tol = float(cfg["track_pair_tol_in"])
    sep_tol = float(cfg["sep_tol_in"])
    target_sep = float(cfg["pair_separation_in"])

    # Pair 1 (RED/BLU)
    red = info["h_in"]["RED"]
    blu = info["h_in"]["BLU"]
    if abs(red - blu) > tol:
        if red > blu:
            flats = max(1, int(round(abs(red - blu) / flat_in)))
            lines.append(f"Lengthen BLU pitch link: +{flats} flats")
        else:
            flats = max(1, int(round(abs(red - blu) / flat_in)))
            lines.append(f"Lengthen RED pitch link: +{flats} flats")

    # Pair 2 (ORG/GRN)
    org = info["h_in"]["ORG"]
    grn = info["h_in"]["GRN"]
    if abs(org - grn) > tol:
        if org > grn:
            flats = max(1, int(round(abs(org - grn) / flat_in)))
            lines.append(f"Lengthen GRN pitch link: +{flats} flats")
        else:
            flats = max(1, int(round(abs(org - grn) / flat_in)))
            lines.append(f"Lengthen ORG pitch link: +{flats} flats")

    # Separation between pairs
    if abs(info["sep_in"] - target_sep) > sep_tol:
        delta = target_sep - info["sep_in"]
        flats = max(1, int(round(abs(delta) / flat_in)))
        if delta > 0:
            lines.append(f"Move ORG/GRN pair DOWN: shorten both {flats} flats")
        else:
            lines.append(f"Move ORG/GRN pair UP: lengthen both {flats} flats")

    lines.append("Re-measure 60NR to validate.")
    return title, _wrap(lines)


def _detail_ground100(runs: Dict[str, dict], cfg: dict) -> Tuple[str, List[str]]:
    m = _pick_state(runs, cfg["state_map"]["ground100"])
    if not m:
        return "100% NR (Ground Bal)", ["No 100% NR ground measurement."]

    amp = float(m.get("lat_1r_ips", m.get("vib_1r_ips", 0.0)) or 0.0)
    ph = float(m.get("lat_1r_phase_deg", m.get("vib_1r_phase_deg", 0.0)) or 0.0)
    limit = float(cfg["ground_ips_limit"])
    ok = amp < limit

    title = "100% NR - Ground Mass Balance"
    lines: List[str] = []
    lines.append(f"Status: {'DONE' if ok else 'NEEDS'}")
    lines.append(f"LAT 1R: {amp:.3f} ips @ {ph:.1f}°")
    lines.append(f"Limit : < {limit:.2f} ips")

    if ok:
        lines.append("No correction required.")
        return title, _wrap(lines)

    ips_per_100g = float(cfg["hub_weight_sensitivity_ips_per_100g"])
    grams = (amp / ips_per_100g) * 100.0
    grams = _round_to(grams, 10)
    corr_deg = (ph + 180.0) % 360.0
    corr_clock = _deg_to_clock(corr_deg)

    lines.append(f"Add HUB weight: ~{int(grams)} g")
    lines.append(f"Place @ {corr_clock} (180° from peak)")
    lines.append(_hub_split_hint(corr_deg))
    lines.append("Re-measure 100NR to validate.")
    return title, _wrap(lines)


def _detail_hover(runs: Dict[str, dict], cfg: dict) -> Tuple[str, List[str]]:
    hover = _pick_state(runs, cfg["state_map"]["hover"])
    gnd = _pick_state(runs, cfg["state_map"]["ground100"])
    if not hover:
        return "Hover (Decision)", ["No hover measurement."]

    amp_h = float(hover.get("lat_1r_ips", hover.get("vib_1r_ips", 0.0)) or 0.0)
    ph_h = float(hover.get("lat_1r_phase_deg", hover.get("vib_1r_phase_deg", 0.0)) or 0.0)
    limit = float(cfg["hover_ips_limit"])
    ok = amp_h < limit

    title = "Hover - Product Balance vs Roll"
    lines: List[str] = []
    lines.append(f"Status: {'DONE' if ok else 'NEEDS'}")
    lines.append(f"LAT 1R: {amp_h:.3f} ips @ {ph_h:.1f}°")
    lines.append(f"Limit : < {limit:.2f} ips")

    if ok:
        lines.append("No correction required.")
        return title, _wrap(lines)

    # Compare angle vs ground (100NR) to decide mass vs blade
    if gnd:
        amp_g = float(gnd.get("lat_1r_ips", gnd.get("vib_1r_ips", 0.0)) or 0.0)
        ph_g = float(gnd.get("lat_1r_phase_deg", gnd.get("vib_1r_phase_deg", 0.0)) or 0.0)
        d = _ang_diff_deg(ph_h, ph_g)
        lines.append(f"Angle vs Ground: Δ={d:.0f}°")
    else:
        amp_g, ph_g, d = 0.0, 0.0, 999.0
        lines.append("No Ground reference available")

    if d <= 30.0:
        # Scenario A: same angle -> hub weights
        ips_per_100g = float(cfg["hub_weight_sensitivity_ips_per_100g"])
        grams = (amp_h / ips_per_100g) * 100.0
        grams = _round_to(grams, 10)
        corr_deg = (ph_h + 180.0) % 360.0
        lines.append("Decision: MASS (Hub) - keep ground bal")
        lines.append(f"Add HUB weight: ~{int(grams)} g")
        lines.append(f"Place @ {_deg_to_clock(corr_deg)}")
        lines.append(_hub_split_hint(corr_deg))
    else:
        # Scenario B: different angle -> product balance
        weights_per_ips = float(cfg["product_weights_per_ips"])
        units = max(1, int(round(amp_h * weights_per_ips)))
        corr_deg = (ph_h + 180.0) % 360.0
        lines.append("Decision: AERO (Blade) - product bal")
        lines.append(f"Add TIP weights: ~{units} units")
        lines.append(f"Place @ {_deg_to_clock(corr_deg)}")
        lines.append("NOTE: tip weights are ~11x hub effect")
        lines.append("      and will affect ground balance")

    lines.append("Re-measure HOVER to validate.")
    return title, _wrap(lines)


def _detail_120k(runs: Dict[str, dict], cfg: dict, *, option_120k: int) -> Tuple[str, List[str]]:
    m = _pick_state(runs, cfg["state_map"]["kias120"])
    if not m:
        return "120 KIAS (Vert)", ["No 120 KIAS measurement."]

    amp = float(m.get("vert_1r_ips", 0.0) or 0.0)
    ph = float(m.get("vert_1r_phase_deg", 0.0) or 0.0)
    limit = float(cfg["kias120_vert_limit"])
    ok = amp < limit

    title = "120 KIAS - Vertical Smoother"
    lines: List[str] = []
    lines.append(f"Status: {'DONE' if ok else 'NEEDS'}")
    lines.append(f"VRT 1R: {amp:.3f} ips @ {ph:.1f}°")
    lines.append(f"Limit : < {limit:.2f} ips")

    if ok:
        lines.append("No correction required.")
        return title, _wrap(lines)

    ips_per_deg = float(cfg["vertical_tab_ips_per_deg"])
    deg = amp / ips_per_deg if ips_per_deg > 0 else 0.0
    deg = max(0.2, _round_to(deg, 0.1))

    blade = _nearest_blade(ph, cfg.get("blade_azimuth_deg", {}))
    opp_blade = _nearest_blade((ph + 180.0) % 360.0, cfg.get("blade_azimuth_deg", {}))

    # User selected option 1
    if option_120k == 1:
        lines.append("Option 1 selected")
        lines.append(f"Bend OUTBD TAB of {blade} UP")
        lines.append(f"Amount: {deg:.1f}°")
    else:
        lines.append("Option 2 selected")
        lines.append(f"Bend OUTBD TAB of {opp_blade} DOWN")
        lines.append(f"Amount: {deg:.1f}°")

    lines.append("Re-measure 120K to validate.")
    return title, _wrap(lines)


def _detail_letdown(runs: Dict[str, dict], cfg: dict) -> Tuple[str, List[str]]:
    m = _pick_state(runs, cfg["state_map"]["letdown"])
    gnd = _pick_state(runs, cfg["state_map"]["ground100"])
    if not m:
        return "Letdown (Trim)", ["No letdown measurement."]

    amp = float(m.get("lat_1r_ips", m.get("vib_1r_ips", 0.0)) or 0.0)
    ph = float(m.get("lat_1r_phase_deg", m.get("vib_1r_phase_deg", 0.0)) or 0.0)
    limit = float(cfg["letdown_ips_limit"])
    ok = amp < limit

    title = "Letdown - Final Trim"
    lines: List[str] = []
    lines.append(f"Status: {'DONE' if ok else 'NEEDS'}")
    lines.append(f"LAT 1R: {amp:.3f} ips @ {ph:.1f}°")
    lines.append(f"Limit : < {limit:.2f} ips")

    if ok:
        lines.append("No correction required.")
        return title, _wrap(lines)

    ips_per_100g = float(cfg["hub_weight_sensitivity_ips_per_100g"])
    ground_limit = float(cfg["ground_ips_limit"])

    # Correction vector to oppose letdown peak
    corr_deg = (ph + 180.0) % 360.0
    grams_full = (amp / ips_per_100g) * 100.0
    grams_full = _round_to(grams_full, 10)

    lines.append(f"Suggested HUB weight: ~{int(grams_full)} g")
    lines.append(f"Place @ {_deg_to_clock(corr_deg)}")
    lines.append(_hub_split_hint(corr_deg))

    # Safety check against ground flat-pitch (100NR)
    if gnd:
        g_amp = float(gnd.get("lat_1r_ips", gnd.get("vib_1r_ips", 0.0)) or 0.0)
        g_ph = float(gnd.get("lat_1r_phase_deg", gnd.get("vib_1r_phase_deg", 0.0)) or 0.0)

        vg = _vec(g_amp, g_ph)
        c_full = _vec(amp, corr_deg)  # amplitude-equivalent correction

        g_new = abs(vg + c_full)
        lines.append(f"Check 100NR: predicted {g_new:.3f} ips")
        lines.append(f"Ground limit: {ground_limit:.2f} ips")

        if g_new > ground_limit:
            # Compromise: 50% correction
            grams_half = _round_to(grams_full * 0.5, 10)
            g_half = abs(vg + (c_full * 0.5))
            l_half = abs(_vec(amp, ph) + (c_full * 0.5))
            lines.append("Safety compromise triggered")
            lines.append(f"Use 50%: ~{int(grams_half)} g")
            lines.append(f"Pred 100NR: {g_half:.3f} ips")
            lines.append(f"Pred LET:  {l_half:.3f} ips")

    lines.append("Re-measure LETDOWN to validate.")
    return title, _wrap(lines)


# -----------------
# Helpers
# -----------------


def _load_cfg() -> dict:
    p = Path(__file__).resolve().parent.parent / "config" / "bht412_mm.json"
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _pick_state(runs: Dict[str, dict], candidates: List[str]) -> Optional[dict]:
    for name in candidates:
        if name in runs:
            return runs[name]
    return None


def _track_checks(m: dict, cfg: dict) -> Tuple[bool, dict]:
    track = m.get("track_rel_mm", {}) or {}
    h_in = {k: (float(track.get(k, 0)) / 25.4) for k in ("RED", "BLU", "ORG", "GRN")}
    rb_diff = h_in["RED"] - h_in["BLU"]
    og_diff = h_in["ORG"] - h_in["GRN"]
    sep = ((h_in["RED"] + h_in["BLU"]) / 2.0) - ((h_in["ORG"] + h_in["GRN"]) / 2.0)

    tol = float(cfg["track_pair_tol_in"])
    sep_tol = float(cfg["sep_tol_in"])
    target_sep = float(cfg["pair_separation_in"])

    ok = (abs(rb_diff) <= tol) and (abs(og_diff) <= tol) and (abs(sep - target_sep) <= sep_tol)
    return ok, {
        "h_in": h_in,
        "rb_diff_in": rb_diff,
        "og_diff_in": og_diff,
        "sep_in": sep,
    }


def _wrap(lines: List[str], width: int = 38) -> List[str]:
    """Naive wrap that keeps LCD lines readable."""
    out: List[str] = []
    for ln in lines:
        s = str(ln)
        while len(s) > width:
            out.append(s[:width])
            s = s[width:]
        out.append(s)
    return out


def _round_to(x: float, step: float) -> float:
    if step <= 0:
        return x
    return round(x / step) * step


def _ang_diff_deg(a: float, b: float) -> float:
    d = (a - b) % 360.0
    if d > 180.0:
        d = 360.0 - d
    return abs(d)


def _deg_to_clock(deg: float) -> str:
    """Convert degrees to nearest half-hour clock label."""
    # 0 deg -> 12:00
    d = deg % 360.0
    hours = d / 30.0
    # nearest half-hour
    half = round(hours * 2.0) / 2.0
    h = int(half) % 12
    h = 12 if h == 0 else h
    if abs(half - int(half)) < 1e-9:
        return f"{h}:00"
    return f"{h}:30"


def _hub_split_hint(corr_deg: float) -> str:
    """Heuristic mapping to blade pairs for training UI."""
    clock = _deg_to_clock(corr_deg)
    # The user examples: 11:30 near center of GRN/ORG, 2:30 near RED/BLU.
    h = int(clock.split(":")[0])
    if h in (11, 12, 1):
        return "Split nearest: GRN/ORG"
    if h in (2, 3, 4):
        return "Split nearest: RED/BLU"
    if h in (5, 6, 7):
        return "Split nearest: BLU/ORG"
    return "Split nearest: GRN/RED"


def _nearest_blade(phase_deg: float, blade_az: Dict[str, float]) -> str:
    if not blade_az:
        return "(BLADE)"
    best = None
    best_d = 1e9
    for blade, az in blade_az.items():
        d = _ang_diff_deg(phase_deg, float(az))
        if d < best_d:
            best_d = d
            best = blade
    return best or "(BLADE)"


def _vec(amp: float, ph_deg: float) -> complex:
    r = math.radians(ph_deg)
    return complex(amp * math.cos(r), amp * math.sin(r))


# -------------------------------------------------
# Backwards-compatible API
# -------------------------------------------------

def diagnose_from_result(
    runs: Dict[str, dict],
    *,
    option_120k: int = 1,
) -> Dict[str, object]:
    """Compatibility wrapper.

    Earlier versions of the app imported ``diagnose_from_result`` from
    ``rads.models``. The new DIAGS workflow is step-based (BHT-412-MM), so this
    function returns a small, UI-friendly bundle:

    - ``summaries``: list of 5 StepSummary objects
    - ``next_step``: first step that is not DONE (or "complete")
    - ``detail``: (title, lines) for the next step
    """

    summaries = step_summaries_for_bht412(runs)

    # Pick the first step that isn't DONE; if all DONE, mark complete.
    next_step = "complete"
    for s in summaries:
        if s.status != "DONE":
            next_step = s.step_id
            break

    if next_step == "complete":
        title = "DIAGS"
        lines = _wrap([
            "All steps DONE.",
            "Rotor within training limits.",
        ])
    else:
        title, lines = step_detail_for_bht412(runs, next_step, option_120k=option_120k)

    return {
        "summaries": summaries,
        "next_step": next_step,
        "detail": (title, lines),
    }
