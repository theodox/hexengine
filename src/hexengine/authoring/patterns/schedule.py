"""
Turn schedule patterns: interleaved faction×phase rotas and registry assembly.
"""

from __future__ import annotations

from collections.abc import Callable

from ...arcs.registry import TurnArcRegistry
from ...arcs.runner import ArcSpec
from ...arcs.schedule import ArcSchedule, ScheduleSlot
from .phase import simple_phase


def routine_arc_id(faction: str, phase: str) -> str:
    return f"{faction}_{phase.lower()}"


def interleaved_slots(
    factions: tuple[str, ...],
    phases: tuple[tuple[str, int, str], ...],
    *,
    faction_first: bool = True,
) -> tuple[ScheduleSlot, ...]:
    """
    Build schedule slots in interleaved rota order.

    When ``faction_first`` is True (hexdemo default), each faction completes all
    phases before the next faction (Union Move, Union Combat, Confederate Move, …).
    When False, each phase cycles all factions before the next phase.
    """

    if not factions:
        raise ValueError("interleaved_slots requires at least one faction")
    rows: list[ScheduleSlot] = []
    if faction_first:
        for faction in factions:
            for phase_name, max_actions, kind in phases:
                rows.append(
                    ScheduleSlot(
                        routine_arc_id(faction, phase_name),
                        faction,
                        phase_name,
                        int(max_actions),
                        kind=str(kind),
                    )
                )
    else:
        for phase_name, max_actions, kind in phases:
            for faction in factions:
                rows.append(
                    ScheduleSlot(
                        routine_arc_id(faction, phase_name),
                        faction,
                        phase_name,
                        int(max_actions),
                        kind=str(kind),
                    )
                )
    return tuple(rows)


def build_turn_registry(
    slots: tuple[ScheduleSlot, ...],
    *,
    allowed_actions_for_phase: Callable[[str], frozenset[str]],
) -> TurnArcRegistry:
    """Assemble a TurnArcRegistry from slots and a phase→actions map."""

    schedule = ArcSchedule(slots)
    routine_specs: dict[str, ArcSpec] = {}
    for slot in slots:
        arc = simple_phase(
            slot.routine_arc_id,
            allowed_actions=allowed_actions_for_phase(slot.phase),
            kind=slot.kind,
        )
        routine_specs[slot.routine_arc_id] = ArcSpec(arc=arc, owner_resolver=None)
    return TurnArcRegistry(schedule=schedule, routine_specs=routine_specs)


__all__ = [
    "build_turn_registry",
    "interleaved_slots",
    "routine_arc_id",
]
