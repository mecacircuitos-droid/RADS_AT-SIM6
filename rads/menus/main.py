from __future__ import annotations

from typing import List

from rads.core import Key, LCD, RADSState, Screen
from rads.ui.lcd_helpers import header_scientific_atlanta


def register_main(sim: RADSState) -> None:
    sim.screens["main"] = Screen(
        id="main",
        title="MAIN",
        help_text="F1=MEASURE F2=DISPLAY F3=DIAGS F4=MANAGER",
        render=_render,
        handle=_handle,
    )


def _render(sim: RADSState) -> LCD:
    lines = header_scientific_atlanta(sim, "MAIN")
    menu = ["MEASURE", "DISPLAY", "DIAGS", "MANAGER"]
    idx = sim.menu_index % len(menu)
    lines.append("")
    for i, it in enumerate(menu):
        prefix = ">" if i == idx else " "
        lines.append(f"{prefix} {it}")
    lines += ["", "", ""]
    footer = "UP/DN move  DO select  QUIT".ljust(38)
    return LCD(lines=lines, highlight_line=4 + idx, footer=footer)


def _handle(sim: RADSState, key: Key) -> None:
    menu_map = {0: "measure", 1: "display", 2: "diags", 3: "manager"}

    if key in (Key.UP, Key.DOWN):
        sim.menu_index = (sim.menu_index + (1 if key == Key.DOWN else -1)) % 4
        return
    if key == Key.DO:
        sim.push(menu_map[sim.menu_index % 4])
        sim.menu_index = 0
        return

    if key == Key.F1:
        sim.push("measure"); sim.menu_index = 0; return
    if key == Key.F2:
        sim.push("display"); sim.menu_index = 0; return
    if key == Key.F3:
        sim.push("diags"); sim.menu_index = 0; return
    if key == Key.F4:
        sim.push("manager"); sim.menu_index = 0; return

    if key == Key.QUIT:
        sim.menu_index = 0
        return
