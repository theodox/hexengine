"""Importable arc patterns for title pack authors."""

from __future__ import annotations

from .movement import build_movement_arc
from .phase import ROUTINE_SEGMENT, build_routine_phase_arc, simple_phase
from .schedule import build_turn_registry, interleaved_slots, routine_arc_id

__all__ = [
    "ROUTINE_SEGMENT",
    "build_movement_arc",
    "build_routine_phase_arc",
    "build_turn_registry",
    "interleaved_slots",
    "routine_arc_id",
    "simple_phase",
]
