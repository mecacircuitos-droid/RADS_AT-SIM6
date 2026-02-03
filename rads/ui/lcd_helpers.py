from __future__ import annotations

from typing import List

from rads.core import RADSState


def header_scientific_atlanta(sim: RADSState, subtitle: str, version: str = "7.00AD51D") -> List[str]:
    """3-line header reminiscent of RADS-AT printouts."""
    line1 = "SIGNAL PROCESSING SYSTEMS     - SHL"
    line2 = f"RADS-AT  VERSION {version:<11}{sim.now_str():>8}"
    line3 = f"{sim.date_str():<12}{subtitle:>26}"
    return [line1[:38], line2[:38], line3[:38]]


def active_tab_index(sim: RADSState) -> int:
    """Which softkey position (F1..F4) is the current tab."""
    sid = getattr(getattr(sim, "current", None), "id", "")
    if sid.startswith("display"):
        return 1
    if sid.startswith("diags"):
        return 2
    if sid.startswith("manager"):
        return 3
    # main + measure screens default to F1
    return 0


def softkey_labels(sim: RADSState) -> tuple[str, str, str, str]:
    """Labels shown on the LCD above the physical F1..F4 keys."""
    l1, l2, l3, l4 = "MEASURE", "DISPLAY", "DIAGS", "MANAGER"
    sid = getattr(getattr(sim, "current", None), "id", "")

    # On Bell 412 Test Status screen, show SETUP on F1
    if sid == "measure_test_status" and (sim.aircraft_type or "").startswith("412"):
        l1 = "SETUP"
    # On SETUP screen, make F1 read BACK
    elif sid == "measure_setup_412":
        l1 = "BACK"

    return (l1, l2, l3, l4)


def softkey_bar_html(sim: RADSState) -> str:
    """Render the softkey labels line (38 cols) without wrapping.

    Important: the physical buttons remain labelled F1..F4. Only the LCD
    shows the meaning (MEASURE/DISPLAY/DIAGS/MANAGER, or SETUP, etc.).
    """

    labels = list(softkey_labels(sim))
    active = active_tab_index(sim)

    # 4 slots of 8 chars + 3 separators = 35 chars. Fits safely in 38.
    slots = [lbl[:8].center(8) for lbl in labels]
    parts: List[str] = []
    for i, s in enumerate(slots):
        cls = "keyseg on" if i == active else "keyseg"
        parts.append(f"<span class='{cls}'>{s}</span>")
        if i < len(slots) - 1:
            parts.append("<span class='keysep'>|</span>")
    return "".join(parts)
