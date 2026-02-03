from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional
import datetime as _dt

LCD_COLS = 38
LCD_ROWS = 10  # 9 content lines + 1 footer line


def _fit(s: str) -> str:
    s = s or ""
    return (s[:LCD_COLS]).ljust(LCD_COLS)


class Key(str, Enum):
    POWER = "POWER"
    LAMP = "LAMP"
    CONTRAST_UP = "CONTRAST_UP"
    CONTRAST_DN = "CONTRAST_DN"

    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F4 = "F4"

    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"

    DO = "DO"
    QUIT = "QUIT"

    HELP = "HELP"
    PRINT = "PRINT"

    # Keypad
    DIG0 = "0"
    DIG1 = "1"
    DIG2 = "2"
    DIG3 = "3"
    DIG4 = "4"
    DIG5 = "5"
    DIG6 = "6"
    DIG7 = "7"
    DIG8 = "8"
    DIG9 = "9"
    PLUSMINUS = "+/-"
    DOT = "."


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


@dataclass
class LCD:
    """Text-only LCD model with optional inverse-video rows.

    - highlight_line: single inverse row (typical menu highlight)
    - inv_lines: additional inverse rows (e.g., help bars)
    - footer: plain-text footer (escaped)
    - footer_html: trusted HTML footer (not escaped) for segmented menu bar
    """

    lines: List[str] = field(default_factory=list)
    highlight_line: Optional[int] = None  # 0-based index over content lines
    inv_lines: List[int] = field(default_factory=list)
    footer: str = ""
    footer_html: str = ""

    def render_html(self) -> str:
        """Render the LCD using fixed-height text rows.

        We avoid complex boxed HTML inside <pre> because it can wrap and
        break the 38x10 character grid. Each LCD row is a dedicated <div>
        with `white-space: pre` so spacing is preserved.
        """

        content_rows = LCD_ROWS - 1
        content = [_fit(x) for x in self.lines[:content_rows]]
        while len(content) < content_rows:
            content.append(_fit(""))

        footer_txt = _fit(self.footer or "")

        inv = set(self.inv_lines or [])
        rows: List[str] = []
        for i, line in enumerate(content):
            esc = _escape(line)
            cls = "lcd-line"
            if self.highlight_line is not None and i == self.highlight_line:
                cls += " hl"
            elif i in inv:
                cls += " help"
            rows.append(f"<div class='{cls}'>{esc}</div>")

        if self.footer_html:
            rows.append(f"<div class='lcd-line footer'>{self.footer_html}</div>")
        else:
            rows.append(f"<div class='lcd-line footer'>{_escape(footer_txt)}</div>")

        return "<div class='lcd'><div class='lcd-text'>" + "".join(rows) + "</div></div>"


@dataclass
class Screen:
    id: str
    title: str
    help_text: str
    render: Callable[["RADSState"], LCD]
    handle: Callable[["RADSState", Key], None]


@dataclass
class RADSState:
    # device
    powered: bool = True
    lamp: bool = False
    contrast: int = 5  # 0..10

    # navigation
    # Start directly on MEASURE (closer to the real RADS workflow).
    # The project still keeps a legacy "main" screen module, but we don't
    # boot into it.
    stack: List[str] = field(default_factory=lambda: ["measure"])
    screens: Dict[str, Screen] = field(default_factory=dict)

    # selection / workflow
    aircraft_type: str = "412_50"
    aircraft_version: str = "7.1"
    tail_number: str = ""
    flight_plan: str = "INITIAL"
    flight_id: str = "?"

    # generic menu cursor
    menu_index: int = 0
    input_buffer: str = ""

    # simulated data
    # measurements[flight_id][test_state] = dict
    measurements: Dict[str, Dict[str, dict]] = field(default_factory=dict)

    # how many times each test_state has been acquired for a given flight
    # (used to simulate improvement after applying DIAGS corrections)
    acq_counts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    active_test_state: str = ""
    # acquisition workflow (simulated)
    pending_acq: bool = False
    pending_test_state: str = ""
    pending_tacho_rpm: float = 0.0

    last_completed_state: str = ""

    last_message: str = "Listo."

    # DISPLAY menu state
    display_mode: str = "ONE_TEST"  # ONE_TEST | COMPLETE_FLIGHT | TREND | LIMITS | SUMMARY
    display_state: str = ""  # selected test state for DISPLAY
    display_view: str = "REL_TRACK"  # REL_TRACK | POLAR_1R | TABLE
    display_page: int = 0  # paging within DISPLAY summaries (e.g., complete flight)

    # DISPLAY paging/scrolling (for "Complete Flight" comparisons)
    display_page: int = 0

    # DIAGS menu paging
    diags_page: int = 0

    # cached DIAGS output
    diag_title: str = ""
    diag_lines: List[str] = field(default_factory=list)

    # internal: list of known tail numbers
    tail_numbers_by_type: Dict[str, List[str]] = field(default_factory=lambda: {"412_41": [], "412_50": []})

    def now_str(self) -> str:
        return _dt.datetime.now().strftime("%H:%M:%S")

    def date_str(self) -> str:
        return _dt.datetime.now().strftime("%d-%b-%y").upper()

    def push(self, screen_id: str) -> None:
        self.stack.append(screen_id)

    def pop(self) -> None:
        if len(self.stack) > 1:
            self.stack.pop()

    @property
    def current(self) -> Screen:
        return self.screens[self.stack[-1]]

    def dispatch(self, key: Key) -> None:
        # device keys
        if key == Key.POWER:
            # Model the real unit: powering ON resets the workflow view.
            if self.powered:
                self.powered = False
                self.last_message = "Apagado."
                return

            self.powered = True
            self.last_message = "Encendido."

            # Reset UI/workflow state on power-up.
            self.stack = ["measure"]
            self.menu_index = 0
            self.input_buffer = ""

            self.flight_plan = "INITIAL"
            self.flight_id = "?"
            self.active_test_state = ""
            self.pending_acq = False
            self.pending_test_state = ""
            self.pending_tacho_rpm = 0.0

            # DISPLAY
            self.display_mode = "ONE_TEST"
            self.display_state = ""
            self.display_view = "REL_TRACK"
            self.display_page = 0

            # DIAGS
            self.diags_page = 0
            self.diag_title = ""
            self.diag_lines = []
            return
        if not self.powered:
            return

        if key == Key.LAMP:
            self.lamp = not self.lamp
            self.last_message = "Luz ON." if self.lamp else "Luz OFF."
            return
        if key == Key.CONTRAST_UP:
            self.contrast = min(10, self.contrast + 1)
            self.last_message = f"Contraste: {self.contrast}/10"
            return
        if key == Key.CONTRAST_DN:
            self.contrast = max(0, self.contrast - 1)
            self.last_message = f"Contraste: {self.contrast}/10"
            return

        # delegate
        self.current.handle(self, key)
