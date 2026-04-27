"""
Movement-related hooks (movement budget, ZOC, stacking, retreat policy).

Role in turn resolution:

- The authoritative server validates `MoveUnit` requests during a player's turn.
- Movement hooks supply title policy for:
  - movement budget, ZOC, stacking limits
  - retreat obligations and retreat routing constraints
  - retreat legality checks (e.g. distance rule)
- The engine then applies the resulting move as a pure state action.

Thin clients do not execute these hooks; they receive a small subset of movement policy
via `StateUpdate.turn_rules` (e.g. stacking limit) and per-viewer fields (e.g. retreat
obligations) to drive UI previews.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..hexes.types import Hex
from ..state import GameState
from .core import DEFAULT


@dataclass(frozen=True, slots=True)
class MoveContext:
    """Context for validating a single move attempt (normal move or retreat fulfillment)."""
    state: GameState
    unit_id: str
    from_hex: Hex
    to_hex: Hex
    player_faction: str
    is_retreat_fulfillment: bool = False


@dataclass(frozen=True, slots=True)
class StackingPolicy:
    """
    Stacking rules for movement previews and server validation.

    - `limit`: max active units allowed on a hex *at rest*.
    - `friendly_pass_through`: moving units may traverse friendly-occupied hexes.
    - `friendly_end_allowed`: moving units may end on friendly-occupied hexes if under limit.
    """

    limit: int
    friendly_pass_through: bool = True
    friendly_end_allowed: bool = True


@dataclass(frozen=True, slots=True)
class MovementHooks:
    """
    Movement policy surface consulted by the authoritative server during turn resolution.

    Any hook may be omitted. When omitted (or when it returns `DEFAULT`), the engine uses
    its default behavior for that hook point.

    Hooks should not mutate `state`. Return data to guide engine behavior or raise to reject.
    """

    movement_budget_for_unit: Callable[[GameState, str], float | object] | None = None
    zoc_hexes_for_unit: Callable[[GameState, str], frozenset[Hex] | None | object] | None = None
    stacking_policy_for_unit: Callable[[GameState, str], StackingPolicy | object] | None = None
    stacking_limit: Callable[[GameState], int | None | object] | None = None
    retreat_group_unit_ids: Callable[[GameState, str], tuple[str, ...] | object] | None = None
    retreat_obligation_hexes_remaining: Callable[[GameState, str], int | None | object] | None = None
    any_retreat_obligation_pending: Callable[[GameState], bool | object] | None = None
    faction_has_pending_retreat_obligation: Callable[[GameState, str], bool | object] | None = None
    retreat_blocked_hexes: Callable[[GameState, str], frozenset[Hex] | None | object] | None = None
    validate_retreat_move: Callable[[MoveContext, int], None | object] | None = None
    validate_move: Callable[[MoveContext], None | object] | None = None

    def budget(self, state: GameState, unit_id: str) -> float | object:
        if self.movement_budget_for_unit is None:
            return DEFAULT
        return self.movement_budget_for_unit(state, unit_id)

    def zoc(self, state: GameState, unit_id: str) -> frozenset[Hex] | None | object:
        if self.zoc_hexes_for_unit is None:
            return DEFAULT
        return self.zoc_hexes_for_unit(state, unit_id)

    def stacking(self, state: GameState, unit_id: str) -> StackingPolicy | object:
        if self.stacking_policy_for_unit is None:
            return DEFAULT
        return self.stacking_policy_for_unit(state, unit_id)

    def stack_limit(self, state: GameState) -> int | None | object:
        if self.stacking_limit is None:
            return DEFAULT
        return self.stacking_limit(state)

    def retreat_group(self, state: GameState, unit_id: str) -> tuple[str, ...] | object:
        if self.retreat_group_unit_ids is None:
            return DEFAULT
        return self.retreat_group_unit_ids(state, unit_id)

    def retreat_remaining(self, state: GameState, unit_id: str) -> int | None | object:
        if self.retreat_obligation_hexes_remaining is None:
            return DEFAULT
        return self.retreat_obligation_hexes_remaining(state, unit_id)

    def any_retreat_pending(self, state: GameState) -> bool | object:
        if self.any_retreat_obligation_pending is None:
            return DEFAULT
        return self.any_retreat_obligation_pending(state)

    def faction_retreat_pending(self, state: GameState, faction: str) -> bool | object:
        if self.faction_has_pending_retreat_obligation is None:
            return DEFAULT
        return self.faction_has_pending_retreat_obligation(state, faction)

    def retreat_blocked(self, state: GameState, unit_id: str) -> frozenset[Hex] | None | object:
        if self.retreat_blocked_hexes is None:
            return DEFAULT
        return self.retreat_blocked_hexes(state, unit_id)

    def validate_retreat(self, ctx: MoveContext, hexes_remaining: int) -> None | object:
        if self.validate_retreat_move is None:
            return DEFAULT
        return self.validate_retreat_move(ctx, int(hexes_remaining))

    def validate(self, ctx: MoveContext) -> None | object:
        if self.validate_move is None:
            return DEFAULT
        return self.validate_move(ctx)


__all__ = [
    "MoveContext",
    "StackingPolicy",
    "MovementHooks",
]

