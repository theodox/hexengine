"""
Hexdemo turn schedule as a declared arc sequence (composable arcs, Phase 4).

Maps the four-phase Union/Confederate rota to routine phase arcs plus an ArcSchedule.
"""

from __future__ import annotations

from hexengine.arcs import ArcSpec
from hexengine.arcs.registry import TurnArcRegistry
from hexengine.arcs.routine_phase import build_routine_phase_arc
from hexengine.arcs.schedule import ArcSchedule, ScheduleSlot

from .constants import HEXDEMO_FACTIONS

_MOVE_ACTIONS = frozenset(
    {"MoveUnit", "NextPhase", "MoveMarker", "AddMarker", "RemoveMarker"}
)
_COMBAT_ACTIONS = frozenset({"Attack", "NextPhase"})


def _routine_arc_id(faction: str, phase: str) -> str:
    return f"{faction}_{phase.lower()}"


def _allowed_for_phase(phase: str) -> frozenset[str]:
    if phase in ("Move", "Movement"):
        return _MOVE_ACTIONS
    if phase in ("Combat", "Attack"):
        return _COMBAT_ACTIONS
    return frozenset({"NextPhase"})


def hexdemo_schedule_slots(
    factions: tuple[str, ...] = HEXDEMO_FACTIONS,
) -> tuple[ScheduleSlot, ...]:
    """Union Move, Union Combat, Confederate Move, Confederate Combat."""

    if len(factions) < 2:
        raise ValueError("hexdemo schedule requires two factions")
    union, confederate = factions[0], factions[1]
    return (
        ScheduleSlot(_routine_arc_id(union, "Move"), union, "Move", 4, kind="move"),
        ScheduleSlot(
            _routine_arc_id(union, "Combat"), union, "Combat", 2, kind="combat"
        ),
        ScheduleSlot(
            _routine_arc_id(confederate, "Move"), confederate, "Move", 4, kind="move"
        ),
        ScheduleSlot(
            _routine_arc_id(confederate, "Combat"),
            confederate,
            "Combat",
            2,
            kind="combat",
        ),
    )


def build_hexdemo_turn_arc_registry(
    factions: tuple[str, ...] = HEXDEMO_FACTIONS,
) -> TurnArcRegistry:
    """Build the hexdemo turn arc registry (schedule + routine arc specs)."""

    slots = hexdemo_schedule_slots(factions)
    schedule = ArcSchedule(slots)
    routine_specs: dict[str, ArcSpec] = {}
    for slot in slots:
        arc = build_routine_phase_arc(
            slot.routine_arc_id,
            allowed_actions=_allowed_for_phase(slot.phase),
            kind=slot.kind,
        )
        routine_specs[slot.routine_arc_id] = ArcSpec(arc=arc, owner_resolver=None)
    return TurnArcRegistry(schedule=schedule, routine_specs=routine_specs)


__all__ = [
    "build_hexdemo_turn_arc_registry",
    "hexdemo_schedule_slots",
]
