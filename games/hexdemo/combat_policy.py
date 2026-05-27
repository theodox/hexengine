"""Hexdemo policy for blocking routine phase advance during combat substates."""

from __future__ import annotations

from hexengine.state import GameState

from . import combat, title_state


def blocks_routine_phase_advance(state: GameState) -> bool:
    """True when retreat obligations or combat gates forbid End Phase / auto-advance."""

    if combat.any_retreat_obligation_pending(state):
        return True
    gate = str(title_state.bucket(state).get("combat_gate", "")).strip()
    return gate in (
        "awaiting_retreat",
        "awaiting_retreat_or_disrupt",
        "awaiting_advance",
    )


__all__ = ["blocks_routine_phase_advance"]
