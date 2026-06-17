"""
Hexdemo turn schedule — **authoritative rota** for match flow.

``build_hexdemo_turn_arc_registry`` is the single source of truth for when each
faction acts and which routine arc runs. The server reads it from
``ArcHook.TURN_ARC_REGISTRY`` (wired in ``hooks.build_hooks`` from ``game_config``).

Edit ``hexdemo_schedule_slots`` (or ``interleaved_slots`` args) to change the
four-phase Union/Confederate Move/Combat rota.
"""

from __future__ import annotations

from hexengine.authoring.patterns.schedule import (
    build_turn_registry,
    interleaved_slots,
)

from ..constants import HEXDEMO_FACTIONS

_MOVE_ACTIONS = frozenset(
    {"MoveUnit", "NextPhase", "MoveMarker", "AddMarker", "RemoveMarker"}
)
_COMBAT_ACTIONS = frozenset({"Attack", "NextPhase"})


def _allowed_for_phase(phase: str) -> frozenset[str]:
    if phase in ("Move", "Movement"):
        return _MOVE_ACTIONS
    if phase in ("Combat", "Attack"):
        return _COMBAT_ACTIONS
    return frozenset({"NextPhase"})


def hexdemo_schedule_slots(
    factions: tuple[str, ...] = HEXDEMO_FACTIONS,
):
    """Union Move, Union Combat, Confederate Move, Confederate Combat."""

    if len(factions) < 2:
        raise ValueError("hexdemo schedule requires two factions")
    return interleaved_slots(
        factions,
        (
            ("Move", 4, "move"),
            ("Combat", 2, "combat"),
        ),
    )


def build_hexdemo_turn_arc_registry(
    factions: tuple[str, ...] = HEXDEMO_FACTIONS,
):
    """Build the hexdemo turn arc registry (schedule + routine arc specs)."""

    return build_turn_registry(
        hexdemo_schedule_slots(factions),
        allowed_actions_for_phase=_allowed_for_phase,
    )


__all__ = [
    "build_hexdemo_turn_arc_registry",
    "hexdemo_schedule_slots",
]
