"""
Turn schedule helpers: prefer ``TurnArcRegistry`` on title hooks, else ``GameDefinition``.
"""

from __future__ import annotations

from typing import Any

from ...gamedef.protocol import GameDefinition
from ...hooks.title import read_title_hooks_from_definition
from ...state import GameState
from ..registry import TurnArcRegistry
from .lookup import turn_arc_registry_from_hooks


def turn_arc_registry_from_definition(game: GameDefinition) -> TurnArcRegistry | None:
    """Return the title's declared turn arc registry, if any."""

    hooks = read_title_hooks_from_definition(game)
    return turn_arc_registry_from_hooks(hooks)


def turn_order_entries_from_definition(game: GameDefinition) -> list[dict[str, Any]]:
    """Flat rota entries for wire and bootstrap."""

    reg = turn_arc_registry_from_definition(game)
    if reg is not None:
        return reg.schedule.turn_order_entries()
    return list(game.turn_order())


def available_factions_from_definition(game: GameDefinition) -> list[str]:
    """Factions players may join as."""

    reg = turn_arc_registry_from_definition(game)
    if reg is not None:
        return reg.schedule.available_factions()
    return list(game.available_factions())


def initial_turn_slot_from_definition(game: GameDefinition) -> dict[str, Any]:
    """First schedule slot (faction, phase, max_actions) for match bootstrap."""

    order = turn_order_entries_from_definition(game)
    if not order:
        raise ValueError("Turn schedule is empty")
    slot = order[0]
    return {
        "faction": str(slot["faction"]),
        "phase": str(slot["phase"]),
        "max_actions": int(slot["max_actions"]),
    }


def next_phase_from_registry(
    reg: TurnArcRegistry, schedule_index: int
) -> dict[str, Any]:
    """Next schedule slot after ``schedule_index`` (wraps)."""

    slot, next_idx = reg.schedule.next_after(schedule_index)
    return {
        "faction": slot.faction,
        "phase": slot.phase,
        "max_actions": int(slot.max_actions),
        "schedule_index": next_idx,
    }


def next_phase_from_definition(
    game: GameDefinition, state: GameState
) -> dict[str, Any]:
    """Next schedule slot after ``state.turn.schedule_index`` (wraps)."""

    reg = turn_arc_registry_from_definition(game)
    if reg is not None:
        return next_phase_from_registry(reg, int(state.turn.schedule_index))
    return game.get_next_phase(state)


__all__ = [
    "available_factions_from_definition",
    "initial_turn_slot_from_definition",
    "next_phase_from_definition",
    "next_phase_from_registry",
    "turn_arc_registry_from_definition",
    "turn_order_entries_from_definition",
]
