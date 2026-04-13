"""Scenario TOML `[[terrain_groups]]` expands to `LocationRow` list."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from hexengine.hexes.types import Hex, HexColRow
from hexengine.scenarios import load_scenario
from hexengine.scenarios.loader import scenario_to_initial_state


def test_terrain_groups_expand(tmp_path: Path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "g"
            description = ""

            [[terrain_types]]
            terrain = "plain"
            movement_cost = 1.0
            default = true

            [[terrain_groups]]
            terrain = "sand"
            movement_cost = 2.0
            assault_modifier = 0.5
            ranged_modifier = 0.25
            block_los = false
            hex_color = "#c9a227"
            positions = [
              [1, 0],
              [2, -1],
            ]

            [[terrain_groups]]
            terrain = "plain"
            movement_cost = 1.0
            positions = [ [0, 0] ]
            """
        ).strip(),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert len(data.locations) == 3
    sand = [loc for loc in data.locations if loc.terrain_type == "sand"]
    assert len(sand) == 2
    assert sand[0].movement_cost == 2.0
    assert sand[0].assault_modifier == 0.5
    assert sand[0].ranged_modifier == 0.25
    assert sand[0].block_los is False
    assert sand[0].hex_color == "#c9a227"
    assert sand[1].hex_color == "#c9a227"
    plain = [loc for loc in data.locations if loc.terrain_type == "plain"]
    assert len(plain) == 1


def test_terrain_groups_member_hex_color_overrides_group(tmp_path: Path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "g"
            description = ""

            [[terrain_types]]
            terrain = "plain"
            movement_cost = 1.0
            default = true

            [[terrain_groups]]
            terrain = "sand"
            movement_cost = 1.0
            hex_color = "#111111"
            positions = [
              [0, 0],
              { position = [1, 0], hex_color = "#222222" },
            ]
            """
        ).strip(),
        encoding="utf-8",
    )
    data = load_scenario(p)
    by_pos = {loc.position: loc for loc in data.locations}
    assert by_pos[(0, 0)].hex_color == "#111111"
    assert by_pos[(1, 0)].hex_color == "#222222"


def test_terrain_groups_inf_movement_cost(tmp_path: Path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "g"
            description = ""

            [[terrain_types]]
            terrain = "plain"
            movement_cost = 1.0
            default = true

            [[terrain_groups]]
            terrain = "water"
            movement_cost = "inf"
            positions = [
              [1, 2],
            ]
            """
        ).strip(),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert len(data.locations) == 1
    assert data.locations[0].movement_cost == float("inf")


def test_terrain_groups_inherit_all_fields_from_terrain_types(tmp_path: Path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "g"
            description = ""

            [[terrain_types]]
            terrain = "plain"
            movement_cost = 1.0
            default = true

            [[terrain_types]]
            terrain = "forest"
            movement_cost = 4.0
            assault_modifier = 0.5
            ranged_modifier = 0.25
            block_los = false
            hex_color = "#00aa00"

            [[terrain_groups]]
            terrain = "forest"
            positions = [ [0, 0] ]

            [[terrain_groups]]
            terrain = "forest"
            movement_cost = 2.0
            positions = [ [1, 0] ]
            """
        ).strip(),
        encoding="utf-8",
    )
    data = load_scenario(p)
    by_pos = {loc.position: loc for loc in data.locations}
    inh = by_pos[(0, 0)]
    assert inh.movement_cost == 4.0
    assert inh.assault_modifier == 0.5
    assert inh.ranged_modifier == 0.25
    assert inh.block_los is False
    assert inh.hex_color == "#00aa00"
    ov = by_pos[(1, 0)]
    assert ov.movement_cost == 2.0
    assert ov.assault_modifier == 0.5
    assert ov.ranged_modifier == 0.25
    assert ov.block_los is False


def test_map_hex_columns_requires_hex_rows(tmp_path: Path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "g"
            description = ""

            [[terrain_types]]
            terrain = "plain"
            movement_cost = 1.0
            default = true

            [map]
            hex_columns = 5
            """
        ).strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="hex_columns and hex_rows"):
        load_scenario(p)


def test_terrain_groups_member_requires_position(tmp_path: Path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "g"
            description = ""

            [[terrain_types]]
            terrain = "plain"
            movement_cost = 1.0
            default = true

            [[terrain_groups]]
            terrain = "x"
            positions = [
              { terrain = "oops" },
            ]
            """
        ).strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="position"):
        load_scenario(p)


def test_positions_rejects_wrong_tuple_length(tmp_path: Path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "g"
            description = ""

            [[terrain_types]]
            terrain = "plain"
            movement_cost = 1.0
            default = true

            [[terrain_groups]]
            terrain = "x"
            movement_cost = 1.0
            positions = [ [0, 0, 1] ]
            """
        ).strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"\[col, row\]"):
        load_scenario(p)


def test_load_scenario_requires_terrain_types(tmp_path: Path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "g"
            description = ""
            """
        ).strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="terrain_types"):
        load_scenario(p)


def test_load_scenario_rejects_two_default_terrain_types(tmp_path: Path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "g"
            description = ""

            [[terrain_types]]
            terrain = "a"
            movement_cost = 1.0
            default = true

            [[terrain_types]]
            terrain = "b"
            movement_cost = 2.0
            default = true
            """
        ).strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="exactly one"):
        load_scenario(p)


def test_terrain_overlay_hex_color_from_terrain_types_when_group_omits_hex_color(
    tmp_path: Path,
) -> None:
    """[[terrain_groups]] without hex_color still tints using [[terrain_types]].hex_color."""
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "t"
            description = ""

            [[terrain_types]]
            terrain = "plain"
            movement_cost = 1.0
            default = true
            hex_color = "#plainfill"

            [[terrain_types]]
            terrain = "sand"
            movement_cost = 2.0
            hex_color = "#sandfill"

            [[terrain_groups]]
            terrain = "sand"
            positions = [ [0, 0] ]
            """
        ).strip(),
        encoding="utf-8",
    )
    data = load_scenario(p)
    state = scenario_to_initial_state(data, initial_faction="red")
    h = Hex.from_hex_col_row(HexColRow(0, 0))
    loc = state.board.locations[h]
    assert loc.hex_color == "#sandfill"


def test_unset_hex_movement_cost_from_default_terrain_type(tmp_path: Path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "g"
            description = ""

            [[terrain_types]]
            terrain = "mud"
            movement_cost = 2.5
            default = true

            [[terrain_groups]]
            terrain = "road"
            movement_cost = 1.0
            positions = [ [0, 0] ]
            """
        ).strip(),
        encoding="utf-8",
    )
    data = load_scenario(p)
    state = scenario_to_initial_state(data, initial_faction="red")
    assert state.board.get_movement_cost(Hex.from_hex_col_row(HexColRow(5, 5))) == 2.5
    assert state.board.get_movement_cost(Hex.from_hex_col_row(HexColRow(0, 0))) == 1.0
    el = state.board.effective_location(Hex.from_hex_col_row(HexColRow(5, 5)))
    assert el is not None
    assert el.terrain_type == "mud"


def test_unset_effective_location_inherits_combat_fields_from_default_terrain_type(
    tmp_path: Path,
) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "g"
            description = ""

            [[terrain_types]]
            terrain = "mud"
            movement_cost = 2.5
            assault_modifier = 0.1
            ranged_modifier = 0.2
            block_los = false
            default = true

            [[terrain_groups]]
            terrain = "road"
            movement_cost = 1.0
            positions = [ [0, 0] ]
            """
        ).strip(),
        encoding="utf-8",
    )
    data = load_scenario(p)
    state = scenario_to_initial_state(data, initial_faction="red")
    el = state.board.effective_location(Hex.from_hex_col_row(HexColRow(5, 5)))
    assert el is not None
    assert el.assault_modifier == 0.1
    assert el.ranged_modifier == 0.2
    assert el.block_los is False
