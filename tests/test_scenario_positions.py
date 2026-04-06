"""Scenario TOML ``position`` is odd-q ``[col, row]`` only."""

from __future__ import annotations

from hexengine.hexes.types import Hex, HexRowCol
from hexengine.scenarios.parse import _parse_position, _position_to_cube_tuple


def test_parse_position_returns_col_row() -> None:
    assert _parse_position([16, 12]) == (16, 12)


def test_position_to_cube_round_trip() -> None:
    """Parsed pair must match cube for Hex(16, 4, -20)."""
    h = Hex(16, 4, -20)
    rc = HexRowCol.from_hex(h)
    pos = _parse_position([rc.col, rc.row])
    assert _position_to_cube_tuple(pos) == (16, 4, -20)


def test_parse_position_rejects_bad_length() -> None:
    for raw in ([1], [1, 2, 3], [1, 2, 3, 4]):
        try:
            _parse_position(raw)  # type: ignore[arg-type]
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {raw!r}")
