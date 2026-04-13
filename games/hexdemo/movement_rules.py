"""
Stub for future title-owned movement rules (see `movement_rules_delegation` plan).

Keep functions pure: `GameState` in, small values out — no server or client imports.
"""

from __future__ import annotations

from hexengine.hexes.types import Hex
from hexengine.state import DEFAULT_MOVEMENT_BUDGET, GameState


def movement_budget_placeholder(state: GameState, unit_id: str) -> float:
    """Temporary stand-in until `MovementRules` is wired (matches prior hardcoded 4.0)."""
    _ = state, unit_id
    return 3.0


def legal_move_hexes_placeholder(
    state: GameState, unit_id: str, *, movement_budget: float = DEFAULT_MOVEMENT_BUDGET
) -> frozenset[Hex]:
    """Delegate to engine reachability; replace with title policy when `MovementRules` lands."""
    from hexengine.state.logic import compute_valid_moves

    temp_result = compute_valid_moves(state, unit_id, movement_budget)

    # test -- can't move to border hexes
    return frozenset(
        h for h in temp_result if not (h.i == 0 or h.i == 10 or h.j == 0 or h.j == 10)
    )
