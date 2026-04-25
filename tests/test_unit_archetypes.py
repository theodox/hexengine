"""Scenario `unit_archetypes` and auto `id` for `unit_placements`."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from hexengine.scenarios import load_scenario
from hexengine.scenarios.loader import scenario_to_initial_state


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


def test_unit_archetype_graphics_and_squad_override(tmp_path: Path) -> None:
    p = _write_scenario(
        tmp_path,
        """
        [[unit_archetypes]]
        name = "a"
        type = "line_infantry"
        graphics = "soldier"
        faction = "Blue"

        [[unit_placements]]
        archetype = "a"
        graphics = "cavalry_icon"
        positions = [ [0, 0] ]

        [[unit_placements]]
        archetype = "a"
        positions = [ [1, 0] ]
        """,
    )
    data = load_scenario(p)
    assert data.units[0].unit_type == "line_infantry"
    assert data.units[0].graphics == "cavalry_icon"
    assert data.units[1].graphics == "soldier"

    s0 = scenario_to_initial_state(data, initial_faction="Blue")
    ids = [data.units[0].unit_id, data.units[1].unit_id]
    assert s0.board.units[ids[0]].graphics == "cavalry_icon"
    assert s0.board.units[ids[1]].graphics == "soldier"


def test_unit_placements_block_attributes_override_archetype(tmp_path: Path) -> None:
    """Squad-level ``attributes`` (sibling of ``positions``) merges over archetype."""
    p = _write_scenario(
        tmp_path,
        """
        [[unit_archetypes]]
        name = "inf"
        type = "soldier"
        faction = "Red"
        id_prefix = "r"
        attributes = { combat = 6, morale = 5, movement = 6 }

        [[unit_placements]]
        archetype = "inf"
        positions = [[0, 0]]
        attributes = { combat = 5, morale = 4, movement = 6 }
        """,
    )
    data = load_scenario(p)
    assert len(data.units) == 1
    assert data.units[0].attributes == {
        "combat": 5,
        "morale": 4,
        "movement": 6,
    }


def test_unit_archetype_flat_keys_fold_into_attributes(tmp_path: Path) -> None:
    """Flat keys on ``[[unit_archetypes]]`` rows become ``UnitArchetypeRow.attributes``."""
    p = _write_scenario(
        tmp_path,
        """
        [[unit_archetypes]]
        name = "grunt"
        type = "soldier"
        faction = "Red"
        id_prefix = "g"
        combat = 7
        morale = 2

        [[unit_placements]]
        archetype = "grunt"
        positions = [ [0, 0] ]
        """,
    )
    data = load_scenario(p)
    assert data.units[0].attributes == {"combat": 7, "morale": 2}


def test_unit_archetype_flat_keys_override_attributes_table(tmp_path: Path) -> None:
    p = _write_scenario(
        tmp_path,
        """
        [[unit_archetypes]]
        name = "grunt"
        type = "soldier"
        faction = "Red"
        id_prefix = "g"
        attributes = { combat = 1, morale = 9 }
        combat = 6

        [[unit_placements]]
        archetype = "grunt"
        positions = [ [0, 0] ]
        """,
    )
    data = load_scenario(p)
    assert data.units[0].attributes == {"combat": 6, "morale": 9}


def test_unit_archetype_attributes_default_and_merge(tmp_path: Path) -> None:
    p = _write_scenario(
        tmp_path,
        """
        [[unit_archetypes]]
        name = "grunt"
        type = "soldier"
        faction = "Red"
        id_prefix = "g"
        attributes = { role = "line", mp = 4 }

        [[unit_placements]]
        archetype = "grunt"
        positions = [
          [0, 0],
          { position = [1, 0], attributes = { mp = 2, extra = true } },
        ]
        """,
    )
    data = load_scenario(p)
    assert data.units[0].attributes == {"role": "line", "mp": 4}
    assert data.units[1].attributes == {"role": "line", "mp": 2, "extra": True}


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


def test_units_table_attributes(tmp_path: Path) -> None:
    p = _write_scenario(
        tmp_path,
        """
        [[units]]
        id = "u1"
        type = "soldier"
        position = [0, 0]
        faction = "Red"
        attributes = { pinned = true, ap = 3 }
        """,
    )
    data = load_scenario(p)
    assert data.units[0].attributes == {"pinned": True, "ap": 3}
    state = scenario_to_initial_state(
        data, initial_faction="Red", initial_phase="Movement"
    )
    assert state.board.units["u1"].attributes == {"pinned": True, "ap": 3}


def test_unit_placements_position_attributes(tmp_path: Path) -> None:
    p = _write_scenario(
        tmp_path,
        """
        [[unit_placements]]
        type = "soldier"
        faction = "Red"
        positions = [
          { id = "a", position = [0, 0], attributes = { foo = 1 } },
        ]
        """,
    )
    data = load_scenario(p)
    assert data.units[0].unit_id == "a"
    assert data.units[0].attributes == {"foo": 1}


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
