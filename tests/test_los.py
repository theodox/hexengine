from __future__ import annotations

from hexengine.hexes.edges import edge_between
from hexengine.hexes.math import neighbor_hex
from hexengine.hexes.types import Hex
from hexengine.state import (
    GameState,
    get_blocking_hexes,
    has_line_of_sight,
    los_visible_hexes_in_cone,
)
from hexengine.state.game_state import BoardEdgeFeature, BoardState, LocationState


def test_los_blocked_by_edge_feature_on_hex_line() -> None:
    """`edge_line_of_sight_by_tag` blocks LOS along the straight hex segment."""
    a = Hex(0, 0, 0)
    b = Hex(2, 0, -2)
    h1 = Hex(1, 0, -1)
    ek = edge_between(a, h1)
    assert ek is not None
    board = BoardState(
        edge_features=(BoardEdgeFeature(feature_id="r", edge_key=ek, tags=("river",)),),
        edge_line_of_sight_by_tag=(("river", True),),
    )
    state = GameState.create_empty().with_board(board)
    assert has_line_of_sight(state, a, b) is False

    board2 = BoardState(
        edge_features=board.edge_features,
        edge_line_of_sight_by_tag=(("river", False),),
    )
    state2 = GameState.create_empty().with_board(board2)
    assert has_line_of_sight(state2, a, b) is True


def test_los_adjacent_always_clear() -> None:
    state = GameState.create_empty()
    a = Hex(0, 0, 0)
    b = Hex(1, 0, -1)
    assert has_line_of_sight(state, a, b) is True
    assert get_blocking_hexes(state, a, b) == ()


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

    assert get_blocking_hexes(state, a, b) == (blocker,)
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
    assert get_blocking_hexes(state, a, b) == ()


def test_los_visible_hexes_in_cone_filters_blocked_targets() -> None:
    origin = Hex(0, 0, 0)

    blocker = Hex(1, 0, -1)
    behind_blocker = Hex(2, 0, -2)
    off_axis = Hex(1, 1, -2)

    # Find the direction index which points from origin to `blocker`.
    direction = next(d for d in range(6) if neighbor_hex(origin, d) == blocker)

    board = BoardState().with_location(
        LocationState(
            position=blocker,
            terrain_type="forest",
            movement_cost=1.0,
            block_los=True,
        )
    )
    state = GameState.create_empty().with_board(board)

    # Use a wider cone so an off-axis target is included for this test.
    visible = los_visible_hexes_in_cone(
        state,
        origin,
        3,
        direction=direction,
        half_angle=1.0471975512,  # ~= pi/3
    )

    assert origin in visible
    assert blocker in visible  # endpoints do not block LOS
    assert behind_blocker not in visible  # blocked by `blocker`
    assert off_axis in visible  # not on the blocked line
