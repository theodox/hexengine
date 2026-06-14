"""Hexdemo movement_rules parity with hook adapters."""

from __future__ import annotations

from games.hexdemo.hooks import build_hooks
from games.hexdemo.movement import rules as movement_rules

from hexengine.hexes.types import Hex
from hexengine.hooks.modification import MoveContext
from hexengine.state import GameState
from hexengine.state.game_state import BoardState, LocationState, UnitState


def _state_with_unit() -> GameState:
    h = Hex(0, 0, 0)
    board = BoardState(
        locations={
            h: LocationState(position=h, terrain_type="clear", movement_cost=1.0)
        },
        units={
            "u1": UnitState(
                unit_id="u1",
                unit_type="inf",
                faction="union",
                position=h,
                active=True,
                attributes={"movement": 4},
            )
        },
    )
    return GameState.create_empty().with_board(board).with_session_state_key("hexdemo")


def test_movement_budget_reads_unit_attribute() -> None:
    st = _state_with_unit()
    assert movement_rules.movement_budget_for_unit(st, "u1") == 4.0
    hooks = build_hooks()
    assert hooks.modification.movement_budget_for_unit(st, "u1") == 4.0


def test_validate_retreat_move_requires_exact_distance() -> None:
    ctx = MoveContext(
        state=_state_with_unit(),
        unit_id="u1",
        from_hex=Hex(0, 0, 0),
        to_hex=Hex(1, 0, -1),
        player_faction="union",
        is_retreat_fulfillment=True,
    )
    movement_rules.validate_retreat_move(ctx, 1)
    try:
        movement_rules.validate_retreat_move(ctx, 2)
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "exactly 2" in str(e)
