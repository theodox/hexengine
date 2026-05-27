"""Engine catalog default for phase auto-advance after a normal move spends an action."""

from __future__ import annotations

from ..state import GameState


def default_auto_advance_phase_after_move_spend(state: GameState) -> bool:
    """Advance when the current phase action pool is empty (builtin / title default)."""

    return int(state.turn.phase_actions_remaining) <= 0


__all__ = ["default_auto_advance_phase_after_move_spend"]
