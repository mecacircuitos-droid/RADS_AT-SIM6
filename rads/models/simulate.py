from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple


# Bell 412 blade color labels used across the simulator
BLADE_LABELS_412 = ["BLU", "ORG", "RED", "GRN"]


@dataclass(frozen=True)
class TestResult:
    """One simulated acquisition (one test state / one regime)."""

    aircraft_type: str
    tail_number: str
    flight_plan: str
    flight_id: str
    test_state: str
    timestamp_epoch: float

    # Tracking: per-blade relative height (mm) referenced to mean
    track_rel_mm: Dict[str, int]

    # Vibration channels (1/rev), with phases in degrees
    lat_1r_ips: float
    lat_1r_phase_deg: float
    vert_1r_ips: float
    vert_1r_phase_deg: float

    # Legacy fields kept for backward compatibility with early screens
    vib_1r_ips: float
    vib_1r_phase_deg: float
    vib_4r_ips: float
    vib_4r_phase_deg: float


def plan_sequences_for_412() -> Dict[str, List[str]]:
    """Bell 412 simplified scripts aligned with the BHT-412-MM workflow.

    - INITIAL includes the two ground regimes + hover.
    - FLIGHT focuses on 120 KIAS and Letdown trim.
    """

    return {
        "INITIAL": ["60NR", "100NR", "HOVER"],
        "FLIGHT": ["HOVER", "120K", "LETDOWN"],
        "TAIL": ["TR-HOVER", "TR-80K"],
        "SPECTRUM": ["ASPA", "ZOOM"],
        "VIBCHK": ["CHECK"],
    }


def default_next_state(flight_plan: str, completed: List[str]) -> str:
    seq = plan_sequences_for_412().get(flight_plan, [])
    for s in seq:
        if s not in completed:
            return s
    return ""


def simulate_test(
    *,
    aircraft_type: str,
    tail_number: str,
    flight_plan: str,
    flight_id: str,
    test_state: str,
    iteration: int = 0,
) -> TestResult:
    """Generate one simulated acquisition.

    `iteration` is the number of times this test_state has been acquired for the
    same flight. We use it to simulate the effect of applying DIAGS corrections
    between measurements.
    """

    seed = _seed_for(aircraft_type, tail_number, flight_plan, flight_id, test_state)
    rng = random.Random(seed)

    if aircraft_type.startswith("412"):
        track, (lat_amp, lat_ph), (ver_amp, ver_ph), (v4_amp, v4_ph) = _simulate_412_bht(
            test_state=test_state,
            iteration=iteration,
            rng=rng,
        )
    else:
        track, (lat_amp, lat_ph), (ver_amp, ver_ph), (v4_amp, v4_ph) = _simulate_generic(
            test_state=test_state,
            rng=rng,
        )

    # pretend acquisition time
    time.sleep(0.05)

    # Legacy mapping: vib_1r = lateral 1R
    vib_1r = lat_amp
    vib_1r_phase = lat_ph

    return TestResult(
        aircraft_type=aircraft_type,
        tail_number=tail_number,
        flight_plan=flight_plan,
        flight_id=flight_id,
        test_state=test_state,
        timestamp_epoch=time.time(),
        track_rel_mm=track,
        lat_1r_ips=lat_amp,
        lat_1r_phase_deg=lat_ph,
        vert_1r_ips=ver_amp,
        vert_1r_phase_deg=ver_ph,
        vib_1r_ips=vib_1r,
        vib_1r_phase_deg=vib_1r_phase,
        vib_4r_ips=v4_amp,
        vib_4r_phase_deg=v4_ph,
    )


# -------------------------
# Bell 412 BHT-412-MM style
# -------------------------


def _simulate_412_bht(
    *,
    test_state: str,
    iteration: int,
    rng: random.Random,
) -> Tuple[Dict[str, int], Tuple[float, float], Tuple[float, float], Tuple[float, float]]:
    """Deterministic-but-realistic values for the Bell 412 training workflow."""

    # Small repeatable measurement noise
    def n_in(scale: float) -> float:
        return rng.uniform(-scale, scale)

    def n_deg(scale: float) -> float:
        return rng.uniform(-scale, scale)

    def n_ips(scale: float) -> float:
        return rng.uniform(-scale, scale)

    # Track is expressed in inches internally, then converted to mm relative-to-mean
    # so DISPLAY can show it.
    if test_state in ("60NR", "IDLE"):
        # Iteration 0: off-track pairs + wrong separation
        # Iteration 1: pairs aligned, separation still a bit off
        # Iteration 2+: ideal separation 1.75" and pairs aligned
        if iteration <= 0:
            heights_in = {"BLU": 0.55, "RED": 0.85, "ORG": -0.70, "GRN": -0.90}
        elif iteration == 1:
            heights_in = {"BLU": 0.70, "RED": 0.70, "ORG": -0.80, "GRN": -0.80}
        else:
            heights_in = {"BLU": 0.875, "RED": 0.875, "ORG": -0.875, "GRN": -0.875}

        # add tiny noise
        heights_in = {k: v + n_in(0.02) for k, v in heights_in.items()}
        track = _heights_in_to_rel_mm(heights_in)

        lat = (0.05 + n_ips(0.02), (65.0 + n_deg(6.0)) % 360)
        vert = (0.05 + n_ips(0.02), (210.0 + n_deg(8.0)) % 360)
        v4 = (0.06 + n_ips(0.02), (lat[1] + 25.0 + n_deg(10.0)) % 360)
        return track, lat, vert, v4

    # Flat-pitch ground (100% NR): lateral hub imbalance
    if test_state in ("100NR", "FPG"):
        heights_in = {"BLU": 0.70, "RED": 0.70, "ORG": -0.80, "GRN": -0.80}
        if iteration >= 2:
            heights_in = {"BLU": 0.875, "RED": 0.875, "ORG": -0.875, "GRN": -0.875}
        heights_in = {k: v + n_in(0.02) for k, v in heights_in.items()}
        track = _heights_in_to_rel_mm(heights_in)

        if iteration <= 0:
            lat_amp = 0.22 + n_ips(0.02)
        elif iteration == 1:
            lat_amp = 0.09 + n_ips(0.015)
        else:
            lat_amp = 0.06 + n_ips(0.01)
        lat_ph = (70.0 + n_deg(6.0)) % 360

        vert = (0.06 + n_ips(0.015), (240.0 + n_deg(10.0)) % 360)
        v4 = (max(0.02, lat_amp * 0.55 + n_ips(0.01)), (lat_ph + 15.0 + n_deg(10.0)) % 360)
        return track, (round(lat_amp, 3), round(lat_ph, 1)), (round(vert[0], 3), round(vert[1], 1)), (round(v4[0], 3), round(v4[1], 1))

    # Hover: decide hub vs blade aerodynamic; we keep phase close to ground (mass-driven)
    if test_state == "HOVER":
        heights_in = {"BLU": 0.875, "RED": 0.875, "ORG": -0.875, "GRN": -0.875}
        heights_in = {k: v + n_in(0.03) for k, v in heights_in.items()}
        track = _heights_in_to_rel_mm(heights_in)

        if iteration <= 0:
            lat_amp = 0.25 + n_ips(0.03)
        elif iteration == 1:
            lat_amp = 0.10 + n_ips(0.02)
        else:
            lat_amp = 0.07 + n_ips(0.01)
        lat_ph = (80.0 + n_deg(8.0)) % 360

        vert = (0.08 + n_ips(0.02), (200.0 + n_deg(12.0)) % 360)
        v4 = (max(0.02, lat_amp * 0.6 + n_ips(0.01)), (lat_ph + 20.0 + n_deg(12.0)) % 360)
        return track, (round(lat_amp, 3), round(lat_ph, 1)), (round(vert[0], 3), round(vert[1], 1)), (round(v4[0], 3), round(v4[1], 1))

    # 120 KIAS: vertical 1/rev smoother (tabs)
    if test_state in ("120K", "120KIAS"):
        heights_in = {"BLU": 0.90, "RED": 0.85, "ORG": -0.90, "GRN": -0.85}
        # after tab correction, track gets closer to symmetric
        if iteration >= 1:
            heights_in = {"BLU": 0.875, "RED": 0.875, "ORG": -0.875, "GRN": -0.875}
        heights_in = {k: v + n_in(0.03) for k, v in heights_in.items()}
        track = _heights_in_to_rel_mm(heights_in)

        lat = (0.10 + n_ips(0.02), (95.0 + n_deg(10.0)) % 360)

        if iteration <= 0:
            vert_amp = 0.30 + n_ips(0.03)
        elif iteration == 1:
            vert_amp = 0.11 + n_ips(0.02)
        else:
            vert_amp = 0.08 + n_ips(0.01)
        vert_ph = (220.0 + n_deg(10.0)) % 360

        v4 = (max(0.03, vert_amp * 0.55 + n_ips(0.01)), (vert_ph + 35.0 + n_deg(12.0)) % 360)
        return track, (round(lat[0], 3), round(lat[1], 1)), (round(vert_amp, 3), round(vert_ph, 1)), (round(v4[0], 3), round(v4[1], 1))

    # Letdown: lateral shows up when pulling power (fine hub trim)
    if test_state in ("LETDOWN", "LDN", "DESCENT"):
        heights_in = {"BLU": 0.875, "RED": 0.875, "ORG": -0.875, "GRN": -0.875}
        heights_in = {k: v + n_in(0.02) for k, v in heights_in.items()}
        track = _heights_in_to_rel_mm(heights_in)

        if iteration <= 0:
            lat_amp = 0.18 + n_ips(0.02)
        elif iteration == 1:
            # partial correction (safety compromise)
            lat_amp = 0.12 + n_ips(0.02)
        else:
            lat_amp = 0.09 + n_ips(0.01)
        lat_ph = (30.0 + n_deg(8.0)) % 360

        vert = (0.09 + n_ips(0.02), (210.0 + n_deg(15.0)) % 360)
        v4 = (max(0.02, lat_amp * 0.55 + n_ips(0.01)), (lat_ph + 18.0 + n_deg(12.0)) % 360)
        return track, (round(lat_amp, 3), round(lat_ph, 1)), (round(vert[0], 3), round(vert[1], 1)), (round(v4[0], 3), round(v4[1], 1))

    # Other states: keep reasonable defaults
    return _simulate_generic(test_state=test_state, rng=rng)


def _heights_in_to_rel_mm(heights_in: Dict[str, float]) -> Dict[str, int]:
    # Remove mean so values are relative to mean (matches typical RADS display)
    mean = sum(heights_in.values()) / float(len(heights_in) or 1)
    rel_in = {k: (v - mean) for k, v in heights_in.items()}
    return {k: int(round(v * 25.4)) for k, v in rel_in.items()}


# -------------------------
# Generic (non-412) fallback
# -------------------------


def _simulate_generic(
    *,
    test_state: str,
    rng: random.Random,
) -> Tuple[Dict[str, int], Tuple[float, float], Tuple[float, float], Tuple[float, float]]:
    # Track: values roughly -35..+35 mm
    base = {
        "BLU": rng.randint(-10, 25),
        "ORG": rng.randint(-25, 10),
        "RED": rng.randint(-10, 25),
        "GRN": rng.randint(-25, 10),
    }

    noise_scale = {
        "IDLE": 6,
        "FPG": 10,
        "HOVER": 12,
        "40K": 10,
        "80K": 12,
        "120K": 14,
        "TR-HOVER": 8,
        "TR-80K": 10,
        "ASPA": 0,
        "ZOOM": 0,
        "CHECK": 8,
    }.get(test_state, 10)

    track = {k: int(v + rng.randint(-noise_scale, noise_scale)) for k, v in base.items()}

    lat_1r = round(rng.uniform(0.06, 0.55), 3)
    lat_ph = round(rng.uniform(0, 359.9), 1)
    vert_1r = round(max(0.01, lat_1r * rng.uniform(0.4, 1.1)), 3)
    vert_ph = round((lat_ph + rng.uniform(-60, 60)) % 360, 1)
    v4 = round(max(0.01, lat_1r * rng.uniform(0.3, 1.0)), 3)
    v4_ph = round((lat_ph + rng.uniform(-40, 40)) % 360, 1)

    return track, (lat_1r, lat_ph), (vert_1r, vert_ph), (v4, v4_ph)


def _seed_for(*parts: str) -> int:
    s = "|".join(parts)
    # stable, cross-run seed
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) % (2**32)
    return int(h)
