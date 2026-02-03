from __future__ import annotations

import json
from pathlib import Path
from typing import List

from rads.core import Key, LCD, RADSState, Screen
from rads.ui.lcd_helpers import header_scientific_atlanta


def register_manager(sim: RADSState) -> None:
    sim.screens["manager"] = Screen(
        id="manager",
        title="MANAGER",
        help_text="Session management",
        render=_render_main,
        handle=_handle_main,
    )
    sim.screens["manager_status"] = Screen(
        id="manager_status",
        title="MANAGER / STATUS",
        help_text="Summary of the current session",
        render=_render_status,
        handle=_handle_status,
    )
    sim.screens["manager_reset"] = Screen(
        id="manager_reset",
        title="MANAGER / RESET",
        help_text="Reset confirmation",
        render=_render_reset,
        handle=_handle_reset,
    )


def _render_main(sim: RADSState) -> LCD:
    lines = header_scientific_atlanta(sim, "MANAGER")
    items = ["Status", "Reset Session"]
    idx = sim.menu_index % len(items)
    lines.append("")
    for i, it in enumerate(items):
        prefix = ">" if i == idx else " "
        lines.append(f"{prefix} {it}"[:38])
    lines += ["", "(Export is via Streamlit sidebar)", ""]
    return LCD(lines=lines, highlight_line=4 + idx, footer="UP/DN  DO  QUIT".ljust(38))


def _handle_main(sim: RADSState, key: Key) -> None:
    if key == Key.F1:
        sim.push("measure"); sim.menu_index = 0; return
    if key == Key.F2:
        sim.push("display"); sim.menu_index = 0; return
    if key == Key.F3:
        sim.push("diags"); sim.menu_index = 0; return

    if key in (Key.UP, Key.DOWN):
        sim.menu_index = (sim.menu_index + (1 if key == Key.DOWN else -1)) % 2
        return

    if key == Key.DO:
        if sim.menu_index % 2 == 0:
            sim.push("manager_status"); sim.menu_index = 0; return
        sim.push("manager_reset"); sim.menu_index = 0; return

    if key == Key.QUIT:
        sim.pop(); sim.menu_index = 0
        return


def _render_status(sim: RADSState) -> LCD:
    lines = header_scientific_atlanta(sim, "Status")
    flights = len(sim.measurements)
    runs = sum(len(v) for v in sim.measurements.values())
    tails = len(sim.tail_numbers_by_type.get(sim.aircraft_type, []))
    lines += [
        "",
        f"Aircraft: {sim.aircraft_type} v{sim.aircraft_version}"[:38],
        f"Tail: {sim.tail_number or '-'}"[:38],
        f"Active Flight: {sim.flight_id or '-'}"[:38],
        "",
        f"Flights stored: {flights}"[:38],
        f"Runs stored   : {runs}"[:38],
        f"Known tails   : {tails}"[:38],
    ]
    return LCD(lines=lines, highlight_line=None, footer="QUIT".ljust(38))


def _handle_status(sim: RADSState, key: Key) -> None:
    if key == Key.QUIT:
        sim.pop();
        return


def _render_reset(sim: RADSState) -> LCD:
    lines = header_scientific_atlanta(sim, "Reset")
    lines += [
        "",
        "Reset session data?",
        "",
        "[DO] Yes, reset",
        "[QUIT] Cancel",
        "",
        "(tails + measurements)",
        "",
    ]
    return LCD(lines=lines, highlight_line=5, footer="".ljust(38))


def _handle_reset(sim: RADSState, key: Key) -> None:
    if key == Key.QUIT:
        sim.pop();
        return

    if key == Key.DO:
        sim.measurements.clear()
        sim.diag_lines = []
        sim.diag_title = ""
        sim.tail_numbers_by_type = {sim.aircraft_type: []}
        sim.tail_number = ""
        sim.flight_id = "?"
        sim.active_test_state = ""
        sim.last_message = "Session reset"
        sim.pop()
        return
