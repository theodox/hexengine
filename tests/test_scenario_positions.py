"""Scenario TOML position parsing: cube triple vs odd-q pair."""

from __future__ import annotations

from hexengine.scenarios.parse import _parse_position


def test_parse_position_cube_triple() -> None:
    assert _parse_position([16, 4, -20]) == (16, 4, -20)


def test_parse_position_odd_q_pair_matches_cube() -> None:
    """``[col, row]`` odd-q must match cube for Hex(16, 4, -20)."""
    from hexengine.hexes.types import Hex, HexRowCol

    h = Hex(16, 4, -20)
    rc = HexRowCol.from_hex(h)
    assert _parse_position([rc.col, rc.row]) == (16, 4, -20)


def test_parse_position_rejects_bad_length() -> None:
    try:
        _parse_position([1])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
    try:
        _parse_position([1, 2, 3, 4])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
