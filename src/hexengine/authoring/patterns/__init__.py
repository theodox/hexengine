"""Importable arc patterns for title pack authors.

Combat cleanup arcs expose ``combat_gate_panel_actions`` for optional dock rows;
the engine catalog default dock does not inject those buttons.
"""

from __future__ import annotations

from .combat import (
    COMBAT_ARC_ID,
    OWNER_RETREATING,
    SEG_ADVANCE_GATE,
    SEG_CLASSIFY,
    SEG_RESOLVE,
    SEG_RETREAT_GATE,
    SEG_RETREAT_OR_DISRUPT_GATE,
    CombatArcEffectsBinding,
    CombatArcGateUiModes,
    build_combat_cleanup_arc,
    combat_gate_panel_actions,
)
from .movement import build_movement_arc
from .phase import ROUTINE_SEGMENT, build_routine_phase_arc, simple_phase
from .schedule import build_turn_registry, interleaved_slots, routine_arc_id

__all__ = [
    "COMBAT_ARC_ID",
    "CombatArcEffectsBinding",
    "CombatArcGateUiModes",
    "OWNER_RETREATING",
    "ROUTINE_SEGMENT",
    "SEG_ADVANCE_GATE",
    "SEG_CLASSIFY",
    "SEG_RESOLVE",
    "SEG_RETREAT_GATE",
    "SEG_RETREAT_OR_DISRUPT_GATE",
    "build_combat_cleanup_arc",
    "combat_gate_panel_actions",
    "build_movement_arc",
    "build_routine_phase_arc",
    "build_turn_registry",
    "interleaved_slots",
    "routine_arc_id",
    "simple_phase",
]
