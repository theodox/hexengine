"""Protocol for title-specific rules (turn order, factions) hosted by the engine."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..state import GameState


@runtime_checkable
class GameDefinition(Protocol):
    """
    Title-specific rules consulted by GameServer (turn schedule, factions).

    Implementations should be stateless regarding *match* data; do not store
    per-match state on `self` (derive from `hexengine.state.game_state.GameState`
    or inject closures when a title needs session-scoped behavior).

    Optional (for authoritative move validation): `movement_budget_for_unit(state, unit_id)`
    returning the movement cost budget for that unit this phase. If absent, the server
    uses `hexengine.state.logic.DEFAULT_MOVEMENT_BUDGET`.
    """

    def available_factions(self) -> list[str]:
        """Factions players may join as (order may matter for UI)."""
        ...

    def turn_order(self) -> list[dict[str, Any]]:
        """
        Flat turn schedule: each entry has keys `faction`, `phase`, `max_actions`.
        """
        ...

    def get_next_phase(self, state: GameState) -> dict[str, Any]:
        """
        Next schedule slot after the current `state.turn.schedule_index` (wraps).

        Return value includes `faction`, `phase`, `max_actions`, and
        `schedule_index` (the index of the next slot in `turn_order()`).
        """
        ...
