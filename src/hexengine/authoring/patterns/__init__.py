"""Importable arc patterns for title pack authors."""

from __future__ import annotations

from .combat import (
    COMBAT_ARC_ID,
    CombatArcEffectsBinding,
    CombatArcGateKinds,
    OWNER_RETREATING,
    SEG_ADVANCE_GATE,
    SEG_CLASSIFY,
    SEG_RESOLVE,
    SEG_RETREAT_GATE,
    SEG_RETREAT_OR_DISRUPT_GATE,
    build_combat_cleanup_arc,
    build_mandatory_retreat_then_optional_advance_arc,
)
from .movement import build_movement_arc
from .phase import ROUTINE_SEGMENT, build_routine_phase_arc, simple_phase
from .schedule import build_turn_registry, interleaved_slots, routine_arc_id

__all__ = [
    "COMBAT_ARC_ID",
    "CombatArcEffectsBinding",
    "CombatArcGateKinds",
    "OWNER_RETREATING",
    "ROUTINE_SEGMENT",
    "SEG_ADVANCE_GATE",
    "SEG_CLASSIFY",
    "SEG_RESOLVE",
    "SEG_RETREAT_GATE",
    "SEG_RETREAT_OR_DISRUPT_GATE",
    "build_combat_cleanup_arc",
    "build_mandatory_retreat_then_optional_advance_arc",
    "build_movement_arc",
    "build_routine_phase_arc",
    "build_turn_registry",
    "interleaved_slots",
    "routine_arc_id",
    "simple_phase",
]
