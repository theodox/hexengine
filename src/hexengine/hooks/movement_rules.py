"""
Author-facing movement rules protocol.

Titles implement policy in pack-root ``movement_rules.py`` (budget, ZoC, retreat
constraints, step cost, auto-advance policy). The engine owns stepwise payload
open/continue, movement arc cursor sync, and ``WriteHexengineMovementArc``; hook slots
remain thin ``bind_title_hook`` adapters for catalog wiring and preview RPCs.

Stepwise resolution (``resolve_move_as_steps``, interrupt factions) is consulted by the
engine movement bridge; authors do not implement the payload or arc runner directly.
"""

from __future__ import annotations

from typing import Protocol

from ..hexes.types import Hex
from ..state import GameState
from .modification import MoveContext


class MovementRulesBinding(Protocol):
    """Pack-level movement policy surface (maps to ``ModificationHook`` slots)."""

    def movement_budget_for_unit(
        self, state: GameState, unit_id: str
    ) -> float | object: ...

    def zoc_hexes_for_unit(
        self, state: GameState, unit_id: str
    ) -> frozenset[Hex] | object: ...

    def retreat_obligation_hexes_remaining(
        self, state: GameState, unit_id: str
    ) -> int | None: ...

    def any_retreat_obligation_pending(self, state: GameState) -> bool: ...

    def faction_has_pending_retreat_obligation(
        self, state: GameState, faction: str
    ) -> bool: ...

    def retreat_blocked_hexes(
        self, state: GameState, unit_id: str
    ) -> frozenset[Hex]: ...

    def validate_retreat_move(self, ctx: MoveContext, hexes_remaining: int) -> None: ...

    def movement_step_cost_for_unit(
        self,
        state: GameState,
        unit_id: str,
        from_hex: Hex,
        to_hex: Hex,
        base_cost: float,
    ) -> float: ...

    def auto_advance_phase_after_move_spend(self, state: GameState) -> bool: ...


__all__ = ["MovementRulesBinding"]
