"""Scenario TOML ``position`` is odd-q ``[col, row]`` only."""

from __future__ import annotations

import textwrap
from pathlib import Path

from hexengine.hexes.types import Hex, HexColRow
from hexengine.scenarios import load_scenario
from hexengine.scenarios.load.coercion import (
    parse_position,
    position_to_cube_tuple,
)


def test_parse_position_returns_col_row() -> None:
    assert parse_position([16, 12]) == (16, 12)


def test_position_to_cube_round_trip() -> None:
    """Parsed pair must match cube for Hex(16, 4, -20)."""
    h = Hex(16, 4, -20)
    rc = HexColRow.from_hex(h)
    pos = parse_position([rc.col, rc.row])
    assert position_to_cube_tuple(pos) == (16, 4, -20)


def test_parse_position_rejects_bad_length() -> None:
    for raw in ([1], [1, 2, 3], [1, 2, 3, 4]):
        try:
            parse_position(raw)  # type: ignore[arg-type]
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {raw!r}")


def test_grid_hexes_populated_without_hex_columns_rows(tmp_path: Path) -> None:
    """Occupied hexes still get ``grid_hexes`` for tight canvas when [map] omits columns/rows."""
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "g"
            description = ""

            [[terrain_groups]]
            terrain = "plain"
            movement_cost = 1.0
            members = [ { position = [2, 1] } ]
            """
        ).strip(),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert data.map_display.grid_hexes is not None
    assert (2, 0, -2) in data.map_display.grid_hexes
