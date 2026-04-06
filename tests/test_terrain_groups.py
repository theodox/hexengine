"""Scenario TOML ``[[terrain_groups]]`` expands to ``LocationRow`` list."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from hexengine.scenarios.parse import load_scenario


def test_terrain_groups_expand(tmp_path: Path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "g"
            description = ""

            [[terrain_groups]]
            terrain = "sand"
            movement_cost = 2.0
            assault_modifier = 0.5
            ranged_modifier = 0.25
            block_los = false
            hex_color = "#c9a227"
            members = [
              { position = [1, 0] },
              { position = [2, -1] },
            ]

            [[locations]]
            position = [0, 0]
            terrain = "plain"
            movement_cost = 1.0
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

            [[terrain_groups]]
            terrain = "sand"
            movement_cost = 1.0
            hex_color = "#111111"
            members = [
              { position = [0, 0] },
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

            [[terrain_groups]]
            terrain = "water"
            movement_cost = "inf"
            members = [
              { position = [1, 2] },
            ]
            """
        ).strip(),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert len(data.locations) == 1
    assert data.locations[0].movement_cost == float("inf")


def test_map_hex_columns_requires_hex_rows(tmp_path: Path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "g"
            description = ""

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

            [[terrain_groups]]
            terrain = "x"
            members = [
              { terrain = "oops" },
            ]
            """
        ).strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="position"):
        load_scenario(p)
