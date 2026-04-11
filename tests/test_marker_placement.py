"""Tests for marker destination rules (server + preview helpers)."""

from __future__ import annotations

from hexengine.hexes.types import Hex, HexColRow
from hexengine.state.game_state import BoardState, GameState, LocationState, TurnState
from hexengine.state.marker_placement import (
    default_marker_destination_allowed,
    marker_destination_hexes_for_preview,
)


def _state_with_one_plain_hex() -> GameState:
    h = Hex.from_hex_col_row(HexColRow(0, 0))
    loc = LocationState(
        position=h, terrain_type="plain", movement_cost=1.0, hex_color=None
    )
    board = BoardState(locations={h: loc}, units={})
    turn = TurnState("Red", "Movement", 2)
    return GameState(board=board, turn=turn)


def test_default_allows_empty_board_hex() -> None:
    state = _state_with_one_plain_hex()
    h = Hex.from_hex_col_row(HexColRow(0, 0))
    assert default_marker_destination_allowed(state, {}, h) is True


def test_default_rejects_hex_with_unit() -> None:
    state = _state_with_one_plain_hex()
    h = Hex.from_hex_col_row(HexColRow(0, 0))
    from hexengine.state.game_state import UnitState

    u = UnitState(
        unit_id="u1", unit_type="x", faction="Red", position=h, health=10, active=True
    )
    state = GameState(board=state.board.with_unit(u), turn=state.turn)
    assert default_marker_destination_allowed(state, {}, h) is False


def test_preview_set_matches_default_rule() -> None:
    state = _state_with_one_plain_hex()
    h = Hex.from_hex_col_row(HexColRow(0, 0))
    s = marker_destination_hexes_for_preview(state, None, None)
    assert s == {h}
