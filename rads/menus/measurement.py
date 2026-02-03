from __future__ import annotations

import random
import textwrap
from typing import List

from rads.core import Key, LCD, RADSState, Screen
from rads.ui.lcd_helpers import header_scientific_atlanta, softkey_bar_html
from rads.models.simulate import plan_sequences_for_412, default_next_state


# -----------------
# Configuration
# -----------------

AIRCRAFT_TYPES = [
    ("412_50", "7.1"),
    ("412_41", "5.21"),
    ("206B", "7.00"),
    ("206L", "7.00"),
    ("206LF", "7.00"),
    ("212", "7.1"),
    ("407", "7.10"),
    ("407DS", "7.00b"),
    ("ENC250", "7.00"),
    ("FFT", "1.1"),
    ("TRAC", "7.00"),
    ("UH1", "7.00"),
]

PLANS = ["INITIAL", "FLIGHT", "TAIL", "SPECTRUM", "VIBCHK"]


SETUP_412_TEXT = """
ACCELEROMETERS:
1. Install Lat accel @ panel in front of the pilot with wire connector pointed to right; connect to ACC1.
2. Install Vert accel @ panel in front of the pilot with wire connector down; connect to ACC2.
3. Install F/A accel @ panel with connector forward; connect to ACC3.

TRACKER:
1. Install tracker mount on left nose. Install tracker to mount with arrow in direction rotor 100TQs.
2. Tracker angle to be 45 degrees to horizon (42 degrees to floor).
3. Connect tracker cable to tracker and route thru copilots door. Be sure not to block the static ports.
4. Connect other end of tracker cable to Tracker 1 on the DAU.

MAGNETIC PICKUP:
1. Install magnetic pickup and set gap to approximately .050 inches.
2. Verify that green blade is over nose when interrupter is over mag pickup. Correct if necessary.
3. Connect ships magnetic pickup cable to the magnetic pickup.
4. Connect magnetic pickup cable to receptacle at copilots right heel and to Tacho 1 on the DAU.

EQUIPMENT:
1. Connect Power and CADU to DAU.

412_50D/S - HP DRIVE SHAFT BALANCING:
ACCELEROMETERS:
1. Install lat accel on CBOX (wire pointed to the right); connect to ACC3 on the DAU.
2. Install lat accel (CH4) on XMSN (wire pointed to the right); connect to ACC4 on the DAU.

OPTICAL INTERRUPTER:
1. Install optical interrupter on firewall pointing down @ shaft.
2. Align reflective tape on shaft to light optical interrupter LED.
3. Connect optical interrupter cable to TACHO 2 on DAU.

EQUIPMENT:
1. Connect Power and CADU to DAU.
""".strip()


def _wrap_38(paragraph: str) -> List[str]:
    out: List[str] = []
    for raw in paragraph.splitlines():
        line = raw.rstrip()
        if not line:
            out.append("")
            continue
        if line.endswith(":"):
            out.append(line)
            continue
        wrapped = textwrap.wrap(line, width=38, break_long_words=True, break_on_hyphens=True)
        out.extend(wrapped if wrapped else [""])
    return [x[:38].ljust(38) for x in out]


SETUP_412_LINES = _wrap_38(SETUP_412_TEXT)


# -----------------
# Registration
# -----------------


def register_measurement(sim: RADSState) -> None:
    sim.screens["measure"] = Screen(
        id="measure",
        title="MEASURE",
        help_text="Workflow: Aircraft → Tail → Plan → Tests → Start",
        render=_render_main,
        handle=_handle_main,
    )

    sim.screens["measure_select_aircraft"] = Screen(
        id="measure_select_aircraft",
        title="MEASURE / AIRCRAFT",
        help_text="Pick aircraft type",
        render=_render_aircraft,
        handle=_handle_aircraft,
    )

    sim.screens["measure_select_tail"] = Screen(
        id="measure_select_tail",
        title="MEASURE / TAIL",
        help_text="Pick or create a tail number",
        render=_render_tail_select,
        handle=_handle_tail_select,
    )

    sim.screens["measure_entry_tail"] = Screen(
        id="measure_entry_tail",
        title="MEASURE / TAIL ENTRY",
        help_text="Keypad input",
        render=_render_tail_entry,
        handle=_handle_tail_entry,
    )

    sim.screens["measure_select_plan"] = Screen(
        id="measure_select_plan",
        title="MEASURE / PLAN",
        help_text="Pick flight plan",
        render=_render_plan,
        handle=_handle_plan,
    )

    sim.screens["measure_entry_flightid"] = Screen(
        id="measure_entry_flightid",
        title="MEASURE / FLIGHT ID",
        help_text="Keypad input",
        render=_render_flightid_entry,
        handle=_handle_flightid_entry,
    )

    sim.screens["measure_select_test"] = Screen(
        id="measure_select_test",
        title="MEASURE / TESTS",
        help_text="Select test state and start measurement",
        render=_render_test_select,
        handle=_handle_test_select,
    )

    sim.screens["measure_test_status"] = Screen(
        id="measure_test_status",
        title="TEST STATUS",
        help_text="Idle status. DO=start measurement. F1=setup (412)",
        render=_render_test_status,
        handle=_handle_test_status,
    )

    sim.screens["measure_measuring"] = Screen(
        id="measure_measuring",
        title="MEASURING",
        help_text="Acquiring...",
        render=_render_measuring,
        handle=_handle_measuring,
    )

    sim.screens["measure_acq_done"] = Screen(
        id="measure_acq_done",
        title="ACQ DONE",
        help_text="Acquisition complete",
        render=_render_acq_done,
        handle=_handle_acq_done,
    )

    sim.screens["measure_setup_412"] = Screen(
        id="measure_setup_412",
        title="SETUP 412",
        help_text="Bell 412 sensor installation",
        render=_render_setup_412,
        handle=_handle_setup_412,
    )


# -----------------
# Main MEASURE page (9 content lines + footer tab bar)
# -----------------


def _render_main(sim: RADSState) -> LCD:
    lines = header_scientific_atlanta(sim, "MEASURE")

    flight_id = sim.flight_id or "?"
    tail = sim.tail_number or ""
    plan = sim.flight_plan or "INITIAL"

    items = [
        f"Aircraft Type   {sim.aircraft_type:<7}{sim.aircraft_version:>6}",
        f"Tail Number     {tail}",
        f"Flight Plan     {plan}",
        f"Flight I.D.     {flight_id}",
    ]

    idx = sim.menu_index % len(items)
    for it in items:
        lines.append((" " + it)[:38].ljust(38))

    # help bar (inverse)
    lines.append("[DO]   = Select Highlighted Item"[:38].ljust(38))
    lines.append("[QUIT] = Clear Highlighted Item"[:38].ljust(38))

    return LCD(
        lines=lines[:9],
        highlight_line=3 + idx,
        inv_lines=[7, 8],
        footer_html=softkey_bar_html(sim),
    )


def _handle_main(sim: RADSState, key: Key) -> None:
    items_count = 4

    # global tabs
    if key == Key.F2:
        sim.push("display"); sim.menu_index = 0; return
    if key == Key.F3:
        sim.push("diags"); sim.menu_index = 0; return
    if key == Key.F4:
        sim.push("manager"); sim.menu_index = 0; return

    if key in (Key.UP, Key.DOWN):
        sim.menu_index = (sim.menu_index + (1 if key == Key.DOWN else -1)) % items_count
        return

    if key == Key.DO:
        idx = sim.menu_index % items_count
        if idx == 0:
            sim.push("measure_select_aircraft")
        elif idx == 1:
            sim.push("measure_select_tail")
        elif idx == 2:
            # Always default the cursor to INITIAL when entering the plan list.
            # This matches the training screenshots (INITIAL highlighted by default).
            sim.menu_index = 0
            sim.push("measure_select_plan")
        elif idx == 3:
            sim.push("measure_entry_flightid")
        return

    if key == Key.QUIT:
        idx = sim.menu_index % items_count
        if idx == 0:
            sim.aircraft_type = "412_50"
            sim.aircraft_version = "7.1"
            sim.last_message = "Aircraft reset to 412_50"
            return
        if idx == 1 and sim.tail_number:
            sim.tail_number = ""
            sim.last_message = "Tail number cleared"
            return
        if idx == 2 and sim.flight_plan:
            sim.flight_plan = "INITIAL"
            sim.active_test_state = ""
            sim.last_message = "Flight plan reset"
            return
        if idx == 3 and sim.flight_id and sim.flight_id != "?":
            sim.flight_id = "?"
            sim.last_message = "Flight ID cleared"
            return

        sim.pop()
        sim.menu_index = 0


# -----------------
# Aircraft selection (3 per page)
# -----------------


def _render_aircraft(sim: RADSState) -> LCD:
    lines = header_scientific_atlanta(sim, "Aircraft Types")

    per_page = 3
    idx = sim.menu_index % len(AIRCRAFT_TYPES)
    start = (idx // per_page) * per_page
    view = AIRCRAFT_TYPES[start:start + per_page]

    pages = ((len(AIRCRAFT_TYPES) - 1) // per_page) + 1
    page = (start // per_page) + 1
    lines.append(f"PAGE {page} OF {pages}"[:38].ljust(38))
    for typ, ver in view:
        lines.append(f"{typ:<8}{ver:>6}"[:38].ljust(38))

    # help bar
    lines.append("UP/DN Move   DO Select"[:38].ljust(38))
    lines.append("QUIT Exit"[:38].ljust(38))

    return LCD(
        lines=lines[:9],
        highlight_line=4 + (idx - start),
        inv_lines=[7, 8],
        footer_html=softkey_bar_html(sim),
    )


def _handle_aircraft(sim: RADSState, key: Key) -> None:
    if key in (Key.UP, Key.DOWN):
        sim.menu_index = (sim.menu_index + (1 if key == Key.DOWN else -1)) % len(AIRCRAFT_TYPES)
        return

    # page jump
    if key in (Key.LEFT, Key.RIGHT):
        per_page = 3
        delta = per_page if key == Key.RIGHT else -per_page
        sim.menu_index = (sim.menu_index + delta) % len(AIRCRAFT_TYPES)
        return

    if key == Key.DO:
        typ, ver = AIRCRAFT_TYPES[sim.menu_index % len(AIRCRAFT_TYPES)]
        sim.aircraft_type = typ
        sim.aircraft_version = ver
        sim.tail_numbers_by_type.setdefault(typ, [])
        sim.last_message = f"Aircraft set: {typ}"
        sim.menu_index = 0
        sim.pop()
        return

    if key == Key.QUIT:
        sim.menu_index = 0
        sim.pop()


# -----------------
# Tail selection (3 per page)
# -----------------


def _render_tail_select(sim: RADSState) -> LCD:
    lines = header_scientific_atlanta(sim, "Select Tail No.")

    tails = sim.tail_numbers_by_type.get(sim.aircraft_type, [])
    options = ["NEW"] + tails

    per_page = 3
    idx = sim.menu_index % len(options)
    start = (idx // per_page) * per_page
    view = options[start:start + per_page]

    lines.append("PAGE 1 OF 1"[:38].ljust(38))
    for opt in view:
        lines.append(f"{opt}"[:38].ljust(38))

    # help bar
    lines.append("DO Select"[:38].ljust(38))
    lines.append("QUIT Exit"[:38].ljust(38))

    return LCD(
        lines=lines[:9],
        highlight_line=4 + (idx - start),
        inv_lines=[7, 8],
        footer_html=softkey_bar_html(sim),
    )


def _handle_tail_select(sim: RADSState, key: Key) -> None:
    tails = sim.tail_numbers_by_type.get(sim.aircraft_type, [])
    options = ["NEW"] + tails

    if key in (Key.UP, Key.DOWN):
        sim.menu_index = (sim.menu_index + (1 if key == Key.DOWN else -1)) % len(options)
        return

    if key == Key.DO:
        chosen = options[sim.menu_index % len(options)]
        if chosen == "NEW":
            sim.input_buffer = ""
            sim.push("measure_entry_tail")
        else:
            sim.tail_number = chosen
            sim.last_message = f"Tail set: {chosen}"
            sim.menu_index = 0
            sim.pop()
        return

    if key == Key.QUIT:
        sim.menu_index = 0
        sim.pop()


def _render_tail_entry(sim: RADSState) -> LCD:
    lines = header_scientific_atlanta(sim, "Entry Tail")
    buf = sim.input_buffer or ""

    lines.append("".ljust(38))
    lines.append("Enter new tail number:"[:38].ljust(38))
    lines.append(f"Tail No: {buf}"[:38].ljust(38))
    lines.append("".ljust(38))

    # help bar (inverse)
    lines.append("[DO] Save   [QUIT] Cancel"[:38].ljust(38))
    lines.append("LEFT=Backspace  Digits=Type"[:38].ljust(38))

    return LCD(lines=lines[:9], highlight_line=None, inv_lines=[7, 8], footer_html=softkey_bar_html(sim))


def _handle_tail_entry(sim: RADSState, key: Key) -> None:
    if key == Key.QUIT:
        sim.input_buffer = ""
        sim.pop()
        return

    if key == Key.DO:
        value = (sim.input_buffer or "").strip()
        if value:
            sim.tail_number = value
            tails = sim.tail_numbers_by_type.setdefault(sim.aircraft_type, [])
            if value not in tails:
                tails.insert(0, value)
        sim.input_buffer = ""
        sim.last_message = f"Tail saved: {sim.tail_number or '-'}"

        # close entry + selection screen (back to MEASURE main)
        sim.pop()
        if sim.stack and sim.current.id == "measure_select_tail":
            sim.pop()
        sim.menu_index = 0
        return

    # keypad editing
    if key.value.isdigit():
        sim.input_buffer += key.value
        return
    if key == Key.DOT:
        sim.input_buffer += "."
        return
    if key == Key.PLUSMINUS:
        sim.input_buffer = sim.input_buffer[1:] if sim.input_buffer.startswith("-") else ("-" + sim.input_buffer)
        return
    if key == Key.LEFT:
        sim.input_buffer = sim.input_buffer[:-1]


# -----------------
# Plan selection (3 per page)
# -----------------


def _render_plan(sim: RADSState) -> LCD:
    lines = header_scientific_atlanta(sim, "Flight Plans")

    per_page = 3
    idx = sim.menu_index % len(PLANS)
    start = (idx // per_page) * per_page
    view = PLANS[start:start + per_page]

    lines.append("".ljust(38))
    for p in view:
        lines.append(p[:38].ljust(38))

    # help bar
    lines.append("UP/DN Move   DO Select"[:38].ljust(38))
    lines.append("QUIT Exit"[:38].ljust(38))

    return LCD(
        lines=lines[:9],
        highlight_line=4 + (idx - start),
        inv_lines=[7, 8],
        footer_html=softkey_bar_html(sim),
    )


def _handle_plan(sim: RADSState, key: Key) -> None:
    if key in (Key.UP, Key.DOWN):
        sim.menu_index = (sim.menu_index + (1 if key == Key.DOWN else -1)) % len(PLANS)
        return

    if key == Key.DO:
        sim.flight_plan = PLANS[sim.menu_index % len(PLANS)]
        sim.active_test_state = ""
        sim.last_message = f"Plan set: {sim.flight_plan}"
        sim.menu_index = 0
        sim.pop()

        # workflow: jump to test list
        sim.push("measure_select_test")
        sim.menu_index = 0
        return

    if key == Key.QUIT:
        sim.menu_index = 0
        sim.pop()


# -----------------
# Flight ID entry (compact)
# -----------------


def _render_flightid_entry(sim: RADSState) -> LCD:
    lines = header_scientific_atlanta(sim, "Flight I.D.")

    buf = sim.input_buffer or ("" if sim.flight_id == "?" else sim.flight_id)

    lines.append("".ljust(38))
    lines.append("Enter Flight I.D.:"[:38].ljust(38))
    lines.append(f"ID: {buf}"[:38].ljust(38))
    lines.append("".ljust(38))

    lines.append("[DO] Save   [QUIT] Cancel"[:38].ljust(38))
    lines.append("LEFT=Backspace  Digits=Type"[:38].ljust(38))

    return LCD(lines=lines[:9], highlight_line=None, inv_lines=[7, 8], footer_html=softkey_bar_html(sim))


def _handle_flightid_entry(sim: RADSState, key: Key) -> None:
    if key == Key.QUIT:
        sim.input_buffer = ""
        sim.pop()
        return

    if key == Key.DO:
        v = (sim.input_buffer or "").strip()
        if v:
            sim.flight_id = v
        sim.input_buffer = ""
        sim.last_message = f"Flight ID: {sim.flight_id}"
        sim.pop()
        return

    if key.value.isdigit():
        sim.input_buffer += key.value
        return
    if key == Key.LEFT:
        sim.input_buffer = sim.input_buffer[:-1]


# -----------------
# Test state list + Start (3 states per page)
# -----------------


def _is_412(sim: RADSState) -> bool:
    return sim.aircraft_type.startswith("412")


def _render_test_select(sim: RADSState) -> LCD:
    plan = sim.flight_plan or "INITIAL"
    lines = header_scientific_atlanta(sim, f"{plan} Tests")

    if not _is_412(sim):
        lines.append("".ljust(38))
        lines.append("Tests available for Bell 412."[:38].ljust(38))
        lines.append("Set Aircraft Type to 412_41"[:38].ljust(38))
        lines.append("or 412_50."[:38].ljust(38))
        lines.append("".ljust(38))
        lines.append("QUIT Exit"[:38].ljust(38))
        return LCD(lines=lines[:9], highlight_line=None, inv_lines=[8], footer_html=softkey_bar_html(sim))

    seq = plan_sequences_for_412().get(plan, [])
    if not seq:
        lines.append("".ljust(38))
        lines.append("No tests defined for this plan."[:38].ljust(38))
        lines.append("".ljust(38))
        lines.append("".ljust(38))
        lines.append("".ljust(38))
        lines.append("QUIT Exit"[:38].ljust(38))
        return LCD(lines=lines[:9], highlight_line=None, inv_lines=[8], footer_html=softkey_bar_html(sim))

    completed = list(sim.measurements.get(sim.flight_id, {}).keys()) if sim.flight_id and sim.flight_id != "?" else []

    per_page = 3
    idx = sim.menu_index % len(seq)
    start = (idx // per_page) * per_page
    view = seq[start:start + per_page]

    page = (start // per_page) + 1
    pages = ((len(seq) - 1) // per_page) + 1
    context = f"{sim.aircraft_type:<7} {plan:<8} P{page}/{pages}"
    lines.append(context[:38].ljust(38))

    for s in view:
        status = "DONE" if s in completed else ""
        lines.append(f"{s:<30}{status:>8}"[:38].ljust(38))

    lines.append("[DO] Select Test (Test Status)"[:38].ljust(38))
    lines.append("[QUIT] Exit   [HELP/F1] Setup"[:38].ljust(38))

    return LCD(
        lines=lines[:9],
        highlight_line=4 + (idx - start),
        inv_lines=[7, 8],
        footer_html=softkey_bar_html(sim),
    )


def _handle_test_select(sim: RADSState, key: Key) -> None:
    plan = sim.flight_plan or "INITIAL"
    seq = plan_sequences_for_412().get(plan, []) if _is_412(sim) else []

    if key == Key.QUIT:
        sim.menu_index = 0
        sim.pop()
        return

    if not seq:
        return

    if key in (Key.UP, Key.DOWN):
        sim.menu_index = (sim.menu_index + (1 if key == Key.DOWN else -1)) % len(seq)
        return

    if key in (Key.HELP, Key.F1):
        if _is_412(sim):
            sim.menu_index = 0
            sim.push("measure_setup_412")
        else:
            sim.last_message = "SETUP only for Bell 412"
        return

    if key != Key.DO:
        return

    if not sim.tail_number:
        sim.last_message = "Set Tail Number first"
        return
    if not sim.flight_id or sim.flight_id == "?":
        sim.last_message = "Set Flight I.D. first"
        return

    selected = seq[sim.menu_index % len(seq)]
    sim.active_test_state = selected
    # Simulate the live tachometer value shown on Test Status (IDLE)
    sim.pending_tacho_rpm = round(random.uniform(190.0, 205.0), 2)
    sim.last_message = f"Test selected: {selected} (IDLE)"
    sim.push("measure_test_status")


# -----------------
# Test Status (IDLE) - Setup/Start
# -----------------


def _render_test_status(sim: RADSState) -> LCD:
    plan = sim.flight_plan or "INITIAL"
    completed = list(sim.measurements.get(sim.flight_id, {}).keys()) if sim.flight_id and sim.flight_id != "?" else []

    # Ensure we always have a selected test state (or next suggested)
    state = sim.active_test_state or default_next_state(plan, completed)
    if state and state != sim.active_test_state:
        sim.active_test_state = state

    rpm = sim.pending_tacho_rpm or 0.0
    status = "DONE" if state in completed else "IDLE"

    lines = header_scientific_atlanta(sim, "MEASURING")
    lines.append(f"Tachometer Freq (rpm) = {rpm:>6.2f}"[:38].ljust(38))
    lines.append(f"Flight Plan  : {plan}"[:38].ljust(38))
    lines.append(f"Test State   : {state}   {status}"[:38].ljust(38))
    lines.append("Acquisition No.  01 OF 01"[:38].ljust(38))

    lines.append("[DO] Setup/Start Measurement"[:38].ljust(38))
    if _is_412(sim):
        lines.append("[QUIT] Exit   [F1/HELP] Setup"[:38].ljust(38))
    else:
        lines.append("[QUIT] Exit"[:38].ljust(38))


    return LCD(
        lines=lines[:9],
        highlight_line=None,
        inv_lines=[7, 8],
        footer_html=softkey_bar_html(sim),
    )


def _handle_test_status(sim: RADSState, key: Key) -> None:
    # global tabs
    if key == Key.F2:
        sim.push("display"); sim.menu_index = 0; return
    if key == Key.F3:
        sim.push("diags"); sim.menu_index = 0; return
    if key == Key.F4:
        sim.push("manager"); sim.menu_index = 0; return

    # setup (Bell 412 only)
    if key in (Key.F1, Key.HELP):
        if _is_412(sim):
            sim.menu_index = 0
            sim.push("measure_setup_412")
        else:
            sim.last_message = "SETUP only for Bell 412"
        return

    if key == Key.QUIT:
        # back to test list
        while sim.stack and sim.current.id != "measure_select_test":
            sim.pop()
        return

    if key == Key.DO:
        plan = sim.flight_plan or "INITIAL"
        completed = list(sim.measurements.get(sim.flight_id, {}).keys()) if sim.flight_id and sim.flight_id != "?" else []
        state = sim.active_test_state or default_next_state(plan, completed)

        if not state:
            sim.last_message = "No test state selected"
            return
        if not sim.tail_number:
            sim.last_message = "Set Tail Number first"
            return
        if not sim.flight_id or sim.flight_id == "?":
            sim.last_message = "Set Flight I.D. first"
            return

        # arm acquisition; device UI will auto-run it
        sim.pending_test_state = state
        if not sim.pending_tacho_rpm:
            import random
            sim.pending_tacho_rpm = round(random.uniform(190.0, 205.0), 2)
        sim.pending_acq = True
        sim.last_message = f"Starting {state}..."
        sim.push("measure_measuring")
        return


# -----------------
# Measuring / Done
# -----------------


def _render_measuring(sim: RADSState) -> LCD:
    plan = sim.flight_plan or "INITIAL"
    state = sim.pending_test_state or sim.active_test_state or "-"
    rpm = sim.pending_tacho_rpm or 0.0

    lines = header_scientific_atlanta(sim, "MEASURING")
    lines.append("".ljust(38))
    lines.append(f"Tachometer Freq (rpm) = {rpm:>6.2f}"[:38].ljust(38))
    lines.append(f"Flight Plan  : {plan}"[:38].ljust(38))
    lines.append(f"Test State   : {state}"[:38].ljust(38))
    lines.append("Acquisition No.  01 OF 01"[:38].ljust(38))

    # Fill remaining lines (up to 9)

    return LCD(lines=lines[:9], highlight_line=None, footer_html=softkey_bar_html(sim))


def _handle_measuring(sim: RADSState, key: Key) -> None:
    # Acquisition is performed automatically by the UI layer when pending_acq is True.
    if key == Key.QUIT:
        sim.pending_acq = False
        sim.pending_test_state = ""
        sim.pending_tacho_rpm = 0.0
        sim.pop()


def _render_acq_done(sim: RADSState) -> LCD:
    state = sim.last_completed_state or "-"

    lines = header_scientific_atlanta(sim, "ACQ DONE")
    lines.append("".ljust(38))
    lines.append("All Data Acquired for"[:38].ljust(38))
    lines.append(f"the {state} test state."[:38].ljust(38))
    lines.append("".ljust(38))
    lines.append("You can now leave this"[:38].ljust(38))
    lines.append("test condition. QUIT=Exit"[:38].ljust(38))

    return LCD(lines=lines[:9], highlight_line=None, footer_html=softkey_bar_html(sim))


def _handle_acq_done(sim: RADSState, key: Key) -> None:
    if key == Key.QUIT:
        # back to test list to continue
        while sim.stack and sim.current.id != "measure_select_test":
            sim.pop()
        # auto-highlight next suggested state if available
        plan = sim.flight_plan or "INITIAL"
        seq = plan_sequences_for_412().get(plan, [])
        if sim.active_test_state and sim.active_test_state in seq:
            sim.menu_index = seq.index(sim.active_test_state)
        else:
            sim.menu_index = 0


# -----------------
# Setup screen (Bell 412) - scrollable (3 lines per page)
# -----------------


def _render_setup_412(sim: RADSState) -> LCD:
    # No 3-line "Scientific Atlanta" header here; the real setup pages use the
    # full LCD height for instructions.
    lines: List[str] = []

    view_rows = 7
    max_start = max(0, len(SETUP_412_LINES) - view_rows)
    start = min(max(0, sim.menu_index), max_start)

    lines.append(f"SETUP 412  Line {start+1}/{len(SETUP_412_LINES)}"[:38].ljust(38))
    for ln in SETUP_412_LINES[start:start + view_rows]:
        lines.append(ln[:38].ljust(38))

    # help bar as inverse line
    while len(lines) < 8:
        lines.append("".ljust(38))
    lines.append("UP/DN Scroll     QUIT Back"[:38].ljust(38))

    return LCD(lines=lines[:9], highlight_line=None, inv_lines=[8], footer_html=softkey_bar_html(sim))


def _handle_setup_412(sim: RADSState, key: Key) -> None:
    if key == Key.F1:
        sim.menu_index = 0
        sim.pop()
        return
    view_rows = 7
    max_start = max(0, len(SETUP_412_LINES) - view_rows)

    if key in (Key.QUIT, Key.F1):
        sim.menu_index = 0
        sim.pop()
        return

    if key in (Key.UP, Key.DOWN):
        delta = 1 if key == Key.DOWN else -1
        sim.menu_index = min(max(0, sim.menu_index + delta), max_start)
        return