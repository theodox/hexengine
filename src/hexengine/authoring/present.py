"""
Author-facing presentation builders (re-export ``hexengine.ui.display``).

Titles import from here for dock panels, popups, and banner rows. The engine converts
these dataclasses to wire dicts in ``hexengine.hooks.internal.ui_wire`` — pack code
should not assemble ``schema`` fields by hand.

Runtime server modules must not import this module; use ``hexengine.ui.display`` types
from ``ui_wire`` only.
"""

from __future__ import annotations

from ..ui.display import (
    InformPopup,
    InteractionMessage,
    PanelAction,
    TurnDockPanel,
    inform_popup,
    interaction_message,
    panel_action,
    panel_actions_from_dicts,
    turn_dock_panel,
)

__all__ = [
    "InformPopup",
    "InteractionMessage",
    "PanelAction",
    "TurnDockPanel",
    "inform_popup",
    "interaction_message",
    "panel_action",
    "panel_actions_from_dicts",
    "turn_dock_panel",
]
