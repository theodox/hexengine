"""
Turn schedule from hexengine.authoring patterns (move-only IGO-UGO rota).

Add phases to ``_PHASES`` and extend ``_allowed_for_phase`` when you add combat or
other segments.
"""

from __future__ import annotations

from hexengine.arcs.registry import TurnArcRegistry
from hexengine.authoring.patterns.schedule import (
    build_turn_registry,
    interleaved_slots,
)

from .constants import TEMPLATE_FACTIONS

_MOVE_ACTIONS = frozenset(
    {"MoveUnit", "NextPhase", "MoveMarker", "AddMarker", "RemoveMarker"}
)


def _allowed_for_phase(phase: str) -> frozenset[str]:
    if phase in ("Move", "Movement"):
        return _MOVE_ACTIONS
    return frozenset({"NextPhase"})


def template_schedule_slots(
    factions: tuple[str, ...] = TEMPLATE_FACTIONS,
):
    """Blue Move, Red Move (faction-first interleaved)."""

    return interleaved_slots(
        factions,
        (("Move", 4, "move"),),
        faction_first=True,
    )


def build_template_turn_arc_registry(
    factions: tuple[str, ...] = TEMPLATE_FACTIONS,
) -> TurnArcRegistry:
    return build_turn_registry(
        template_schedule_slots(factions),
        allowed_actions_for_phase=_allowed_for_phase,
    )


__all__ = [
    "build_template_turn_arc_registry",
    "template_schedule_slots",
]
