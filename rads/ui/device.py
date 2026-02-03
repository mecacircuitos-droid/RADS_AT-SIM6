from __future__ import annotations

import streamlit as st
import time
from dataclasses import asdict

from rads.models.simulate import simulate_test, default_next_state

from rads.core import Key, LCD, RADSState


def _press(sim: RADSState, k: Key) -> None:
    sim.dispatch(k)


def render_device(sim: RADSState) -> None:
    """Render CADU-like device chrome + current LCD screen."""

    st.markdown("<div class='rads-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='rads-title'>RADS-AT SIMULATOR</div>", unsafe_allow_html=True)

    c_left, c_lcd, c_right = st.columns([1.05, 3.25, 1.05], gap="large")

    with c_left:
        st.markdown("<div class='power'>", unsafe_allow_html=True)
        st.button("ON", use_container_width=True, disabled=sim.powered, on_click=_press, args=(sim, Key.POWER))
        st.button("OFF", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.POWER))
        st.button("LAMP", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.LAMP))
        st.button("CTRST +", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.CONTRAST_UP))
        st.button("CTRST −", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.CONTRAST_DN))
        st.markdown("</div>", unsafe_allow_html=True)

    with c_lcd:
        lcd = sim.current.render(sim) if sim.powered else LCD(lines=[""], highlight_line=None, footer="")
        st.markdown(lcd.render_html(), unsafe_allow_html=True)
        # DISPLAY plots are now rendered *inside* the LCD as ASCII graphics.

    with c_right:
        st.markdown("<div class='skinny'>", unsafe_allow_html=True)
        st.button("QUIT", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.QUIT))
        st.button("DO", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.DO))
        st.markdown("</div>", unsafe_allow_html=True)

    spacer, farea, spacer2 = st.columns([1.05, 3.25, 1.05], gap="large")
    with farea:
        st.markdown("<div class='fkeys'>", unsafe_allow_html=True)
        f1, f2, f3, f4, lab = st.columns([1, 1, 1, 1, 1.1], gap="small")
        with f1:
            st.button("F1", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.F1))
        with f2:
            st.button("F2", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.F2))
        with f3:
            st.button("F3", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.F3))
        with f4:
            st.button("F4", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.F4))
        with lab:
            st.button("LABEL", use_container_width=True, disabled=True)
        st.markdown("</div>", unsafe_allow_html=True)

    kpad, mid, nav = st.columns([2.2, 1.05, 1.45], gap="large")

    with kpad:
        st.markdown("<div class='keypad'>", unsafe_allow_html=True)
        r1 = st.columns(3, gap="small")
        r2 = st.columns(3, gap="small")
        r3 = st.columns(3, gap="small")
        r4 = st.columns(3, gap="small")
        with r1[0]:
            st.button("7", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.DIG7))
        with r1[1]:
            st.button("8", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.DIG8))
        with r1[2]:
            st.button("9", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.DIG9))
        with r2[0]:
            st.button("4", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.DIG4))
        with r2[1]:
            st.button("5", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.DIG5))
        with r2[2]:
            st.button("6", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.DIG6))
        with r3[0]:
            st.button("1", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.DIG1))
        with r3[1]:
            st.button("2", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.DIG2))
        with r3[2]:
            st.button("3", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.DIG3))
        with r4[0]:
            st.button("+/−", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.PLUSMINUS))
        with r4[1]:
            st.button("0", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.DIG0))
        with r4[2]:
            st.button(".", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.DOT))
        st.markdown("</div>", unsafe_allow_html=True)

    with mid:
        st.button("HELP", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.HELP))
        st.button("PRINT", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.PRINT))

    with nav:
        st.markdown("<div class='navpad'>", unsafe_allow_html=True)
        up = st.columns(3)
        with up[1]:
            st.button("▲", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.UP))
        mid2 = st.columns(3)
        with mid2[0]:
            st.button("◀", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.LEFT))
        with mid2[1]:
            st.button(" ", use_container_width=True, disabled=True)
        with mid2[2]:
            st.button("▶", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.RIGHT))
        dn = st.columns(3)
        with dn[1]:
            st.button("▼", use_container_width=True, disabled=not sim.powered, on_click=_press, args=(sim, Key.DOWN))
        st.markdown("</div>", unsafe_allow_html=True)

    # Auto-complete acquisition: show MEASURING screen briefly then save results.
    if sim.powered and sim.current.id == "measure_measuring" and sim.pending_acq:
        # small delay so the user can see the MEASURING screen
        time.sleep(0.6)

        plan = sim.flight_plan or ""
        completed = list(sim.measurements.get(sim.flight_id, {}).keys()) if sim.flight_id and sim.flight_id != "?" else []
        test_state = sim.pending_test_state or sim.active_test_state or default_next_state(plan, completed)

        if (not sim.tail_number) or (not sim.flight_id) or sim.flight_id == "?" or (not test_state):
            sim.pending_acq = False
            sim.last_message = "Cannot acquire: set Tail/Flight ID/Test"
            # return to MEASURE main
            sim.stack[-1] = "measure"
            st.rerun()

        # How many times have we already acquired this regime for this flight?
        # We use this counter to progressively improve the simulated values,
        # as if the student applied the DIAGS correction between runs.
        counts = sim.acq_counts.setdefault(sim.flight_id, {})
        iteration = int(counts.get(test_state, 0))
        counts[test_state] = iteration + 1

        res = simulate_test(
            aircraft_type=sim.aircraft_type,
            tail_number=sim.tail_number,
            flight_plan=plan,
            flight_id=sim.flight_id,
            test_state=test_state,
            iteration=iteration,
        )
        sim.measurements.setdefault(sim.flight_id, {})[test_state] = asdict(res)
        sim.last_completed_state = test_state

        # mark next recommended state
        completed2 = list(sim.measurements.get(sim.flight_id, {}).keys())
        nxt = default_next_state(plan, completed2)
        sim.active_test_state = nxt or ""

        sim.pending_acq = False
        sim.pending_test_state = ""

        if nxt:
            sim.last_message = f"Saved {test_state}. Next: {nxt}"
        else:
            sim.last_message = f"Saved {test_state}. DIAGS available."

        # show the completion message screen
        sim.stack[-1] = "measure_acq_done"
        st.rerun()

    st.markdown(f"<div class='rads-status'>Estado: {sim.last_message}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
