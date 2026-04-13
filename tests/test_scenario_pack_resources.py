"""Resolve scenario asset paths against `<pack>/resources/` when present."""

from __future__ import annotations

import textwrap
from pathlib import Path

from hexengine.scenarios.load.parse import load_scenario


def test_pack_resources_dir_resolves_map_background(tmp_path: Path) -> None:
    root = tmp_path
    pack = root / "pack"
    scen_dir = pack / "scenarios" / "s1"
    scen_dir.mkdir(parents=True)
    res = pack / "resources"
    res.mkdir(parents=True)
    (res / "bg.png").write_bytes(b"x")
    scen = scen_dir / "scenario.toml"
    scen.write_text(
        textwrap.dedent(
            """
            name = "t"
            description = ""

            [[terrain_types]]
            terrain = "plain"
            movement_cost = 1.0
            default = true

            [map]
            background = "bg.png"
            hex_columns = 2
            hex_rows = 2
            """
        ).strip(),
        encoding="utf-8",
    )
    data = load_scenario(scen, static_root=root)
    assert data.map_display.background.replace("\\", "/") == "pack/resources/bg.png"


def test_pack_resources_preferred_over_scenario_dir(tmp_path: Path) -> None:
    root = tmp_path
    pack = root / "pack"
    scen_dir = pack / "scenarios" / "s1"
    scen_dir.mkdir(parents=True)
    res = pack / "resources"
    res.mkdir(parents=True)
    (res / "x.png").write_bytes(b"from-resources")
    (scen_dir / "x.png").write_bytes(b"from-scenario")
    scen = scen_dir / "scenario.toml"
    scen.write_text(
        textwrap.dedent(
            """
            name = "t"
            description = ""

            [[terrain_types]]
            terrain = "plain"
            movement_cost = 1.0
            default = true

            [map]
            background = "x.png"
            hex_columns = 2
            hex_rows = 2
            """
        ).strip(),
        encoding="utf-8",
    )
    data = load_scenario(scen, static_root=root)
    assert data.map_display.background.replace("\\", "/") == "pack/resources/x.png"


def test_dotdot_path_skips_pack_resources_uses_scenario_parent(tmp_path: Path) -> None:
    root = tmp_path
    pack = root / "pack"
    scen_dir = pack / "scenarios" / "s1"
    scen_dir.mkdir(parents=True)
    res = pack / "resources"
    res.mkdir(parents=True)
    (res / "x.png").write_bytes(b"res")
    sibling = scen_dir.parent / "sibling"
    sibling.mkdir(parents=True)
    (sibling / "y.png").write_bytes(b"ok")
    scen = scen_dir / "scenario.toml"
    scen.write_text(
        textwrap.dedent(
            """
            name = "t"
            description = ""

            [[terrain_types]]
            terrain = "plain"
            movement_cost = 1.0
            default = true

            [map]
            background = "../sibling/y.png"
            hex_columns = 2
            hex_rows = 2
            """
        ).strip(),
        encoding="utf-8",
    )
    data = load_scenario(scen, static_root=root)
    assert (
        data.map_display.background.replace("\\", "/") == "pack/scenarios/sibling/y.png"
    )


def test_flat_scenario_without_pack_resources_uses_scenario_parent(
    tmp_path: Path,
) -> None:
    root = tmp_path
    solo = root / "solo"
    solo.mkdir(parents=True)
    (solo / "m.png").write_bytes(b"z")
    scen = solo / "scenario.toml"
    scen.write_text(
        textwrap.dedent(
            """
            name = "t"
            description = ""

            [[terrain_types]]
            terrain = "plain"
            movement_cost = 1.0
            default = true

            [map]
            background = "m.png"
            hex_columns = 2
            hex_rows = 2
            """
        ).strip(),
        encoding="utf-8",
    )
    data = load_scenario(scen, static_root=root)
    assert data.map_display.background.replace("\\", "/") == "solo/m.png"
