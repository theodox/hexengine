"""
Author-time arc construction: builder, patterns, and validation.

Runtime engine code (server, runner, client) must not import this package except
through hexengine.hooks.internal.authoring_bridge and
hexengine.hooks.internal.contracts (load-time validate).

Titles and tests import from here freely.
"""

from __future__ import annotations

from .builder import ArcBuilder, Case, Effect, Guard, SegmentBuilder, arc, case
from .patterns.phase import ROUTINE_SEGMENT, build_routine_phase_arc, simple_phase
from .present import (
    InformPopup,
    InteractionMessage,
    PanelAction,
    TurnDockPanel,
    inform_popup,
    interaction_message,
    panel_action,
    turn_dock_panel,
)

__all__ = [
    "ArcBuilder",
    "Case",
    "Effect",
    "Guard",
    "InformPopup",
    "InteractionMessage",
    "PanelAction",
    "TurnDockPanel",
    "ROUTINE_SEGMENT",
    "SegmentBuilder",
    "arc",
    "build_routine_phase_arc",
    "case",
    "inform_popup",
    "interaction_message",
    "panel_action",
    "simple_phase",
    "turn_dock_panel",
]
