from __future__ import annotations

from rads.core import RADSState

from rads.menus.measurement import register_measurement
from rads.menus.display import register_display
from rads.menus.diags import register_diags
from rads.menus.manager import register_manager


def register_all(sim: RADSState) -> None:
    """Register all RADS-AT top menus as independent modules."""
    register_measurement(sim)
    register_display(sim)
    register_diags(sim)
    register_manager(sim)
