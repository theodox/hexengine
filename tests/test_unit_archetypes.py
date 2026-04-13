"""Scenario `unit_archetypes` and auto `id` for `unit_placements`."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from hexengine.scenarios import load_scenario


def _write_scenario(tmp_path: Path, body: str) -> Path:
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
            """
        ).strip()
        + "\n\n"
        + textwrap.dedent(body).strip(),
        encoding="utf-8",
    )
    return p


def test_unit_placements_auto_id_bare_positions(tmp_path: Path) -> None:
    p = _write_scenario(
        tmp_path,
        """
        [[unit_placements]]
        type = "soldier"
        faction = "Red"
        positions = [ [0, 0], [1, 0] ]
        """,
    )
    data = load_scenario(p)
    assert [u.unit_id for u in data.units] == ["soldier-Red-1", "soldier-Red-2"]
    assert [u.position for u in data.units] == [(0, 0), (1, 0)]


def test_unit_placements_auto_id_counter_continues_across_groups(
    tmp_path: Path,
) -> None:
    p = _write_scenario(
        tmp_path,
        """
        [[unit_placements]]
        type = "soldier"
        faction = "Red"
        positions = [ [0, 0] ]

        [[unit_placements]]
        type = "soldier"
        faction = "Red"
        positions = [ [2, 0] ]
        """,
    )
    data = load_scenario(p)
    assert [u.unit_id for u in data.units] == ["soldier-Red-1", "soldier-Red-2"]


def test_unit_archetype_and_placements(tmp_path: Path) -> None:
    p = _write_scenario(
        tmp_path,
        """
        [[unit_archetypes]]
        name = "blue_line"
        type = "soldier"
        faction = "Blue"
        id_prefix = "inf"

        [[unit_placements]]
        archetype = "blue_line"
        positions = [ [0, 1], [1, 1] ]
        """,
    )
    data = load_scenario(p)
    assert [u.unit_id for u in data.units] == ["inf-1", "inf-2"]
    assert all(u.unit_type == "soldier" and u.faction == "Blue" for u in data.units)


def test_explicit_id_still_works(tmp_path: Path) -> None:
    p = _write_scenario(
        tmp_path,
        """
        [[unit_placements]]
        type = "soldier"
        faction = "Red"
        positions = [
          { id = "alpha", position = [0, 0] },
          [1, 0],
        ]
        """,
    )
    data = load_scenario(p)
    assert data.units[0].unit_id == "alpha"
    assert data.units[1].unit_id == "soldier-Red-1"


def test_duplicate_unit_id_raises(tmp_path: Path) -> None:
    p = _write_scenario(
        tmp_path,
        """
        [[units]]
        id = "same"
        type = "soldier"
        position = [0, 0]
        faction = "Red"

        [[unit_placements]]
        type = "soldier"
        faction = "Blue"
        positions = [ { id = "same", position = [1, 0] } ]
        """,
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_scenario(p)


def test_archetype_plus_type_raises(tmp_path: Path) -> None:
    p = _write_scenario(
        tmp_path,
        """
        [[unit_archetypes]]
        name = "a"
        type = "soldier"
        faction = "Red"

        [[unit_placements]]
        archetype = "a"
        type = "soldier"
        faction = "Red"
        positions = [ [0, 0] ]
        """,
    )
    with pytest.raises(ValueError, match="archetype and type/faction"):
        load_scenario(p)


def test_unknown_archetype_raises(tmp_path: Path) -> None:
    p = _write_scenario(
        tmp_path,
        """
        [[unit_placements]]
        archetype = "missing"
        positions = [ [0, 0] ]
        """,
    )
    with pytest.raises(ValueError, match="unknown archetype"):
        load_scenario(p)


def test_duplicate_archetype_name_raises(tmp_path: Path) -> None:
    p = _write_scenario(
        tmp_path,
        """
        [[unit_archetypes]]
        name = "dup"
        type = "soldier"
        faction = "Red"

        [[unit_archetypes]]
        name = "dup"
        type = "soldier"
        faction = "Blue"

        [[unit_placements]]
        archetype = "dup"
        positions = [ [0, 0] ]
        """,
    )
    with pytest.raises(ValueError, match="duplicate unit_archetypes"):
        load_scenario(p)
