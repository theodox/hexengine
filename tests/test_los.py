from __future__ import annotations

from hexengine.hexes.types import Hex
from hexengine.state import GameState, has_line_of_sight, los_blocking_hexes
from hexengine.state.game_state import BoardState, LocationState


def test_los_adjacent_always_clear() -> None:
    state = GameState.create_empty()
    a = Hex(0, 0, 0)
    b = Hex(1, 0, -1)
    assert has_line_of_sight(state, a, b) is True
    assert los_blocking_hexes(state, a, b) == ()


def test_los_blocks_on_intermediate_hex_only() -> None:
    a = Hex(0, 0, 0)
    b = Hex(3, 0, -3)
    blocker = Hex(1, 0, -1)

    board = BoardState().with_location(
        LocationState(
            position=blocker,
            terrain_type="forest",
            movement_cost=1.0,
            block_los=True,
        )
    )
    state = GameState.create_empty().with_board(board)

    assert los_blocking_hexes(state, a, b) == (blocker,)
    assert has_line_of_sight(state, a, b) is False


def test_los_does_not_treat_endpoints_as_blocking() -> None:
    a = Hex(0, 0, 0)
    b = Hex(3, 0, -3)

    board = (
        BoardState()
        .with_location(
            LocationState(
                position=a,
                terrain_type="smoke",
                movement_cost=1.0,
                block_los=True,
            )
        )
        .with_location(
            LocationState(
                position=b,
                terrain_type="smoke",
                movement_cost=1.0,
                block_los=True,
            )
        )
    )
    state = GameState.create_empty().with_board(board)

    assert has_line_of_sight(state, a, b) is True
    assert los_blocking_hexes(state, a, b) == ()

