"""Scenario `[[colors]]` and `@name` expansion."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from hexengine.scenarios import load_scenario
from hexengine.scenarios.load.color_palette import (
    apply_scenario_color_constants,
    build_color_palette,
    expand_color_tokens,
)


def test_expand_chained_color_refs() -> None:
    # Same order rule as `build_color_palette` (each row sees prior names only).
    ordered = [
        ("a", "#fff"),
        ("b", "@a"),
        ("c", "linear-gradient(@a, @b)"),
    ]
    out: dict[str, str] = {}
    for n, v in ordered:
        out[n] = expand_color_tokens(v, out, where=n)
    assert out["b"] == "#fff"
    assert out["c"] == "linear-gradient(#fff, #fff)"


def test_build_palette_forward_ref_raises() -> None:
    rows = [
        {"name": "b", "value": "@a"},
        {"name": "a", "value": "#000"},
    ]
    with pytest.raises(ValueError, match="unknown color"):
        build_color_palette(rows)


def test_load_scenario_colors_expand_in_map_and_terrain(tmp_path: Path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "t"
            description = ""

            [[colors]]
            name = "fill"
            value = "#aabbcc"

            [[terrain_types]]
            terrain = "plain"
            movement_cost = 1.0
            default = true
            hex_color = "@fill"

            [map]
            hex_color = "@fill"
            hex_columns = 2
            hex_rows = 2
            """
        ).strip(),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert len(data.colors) == 1
    assert data.colors[0].name == "fill"
    assert data.colors[0].value == "#aabbcc"
    assert data.map_display.hex_color == "#aabbcc"
    assert data.terrain_types[0].hex_color == "#aabbcc"


def test_apply_scenario_color_constants_mutates_nested_dict() -> None:
    data = {
        "name": "x",
        "map": {"hex_color": "@c"},
        "colors": [{"name": "c", "value": "rgb(1,2,3)"}],
    }
    apply_scenario_color_constants(data)
    assert data["map"]["hex_color"] == "rgb(1,2,3)"
    assert data["colors"][0]["value"] == "rgb(1,2,3)"


def test_apply_scenario_color_constants_flat_colors_table(tmp_path: Path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        textwrap.dedent(
            """
            name = "t"
            description = ""

            [colors]
            fill = "#aabbcc"
            stroke = "@fill"

            [[terrain_types]]
            terrain = "plain"
            movement_cost = 1.0
            default = true
            hex_color = "@stroke"

            [map]
            hex_color = "@fill"
            hex_columns = 2
            hex_rows = 2
            """
        ).strip(),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert [r.name for r in data.colors] == ["fill", "stroke"]
    assert data.colors[0].value == "#aabbcc"
    assert data.colors[1].value == "#aabbcc"
    assert data.map_display.hex_color == "#aabbcc"
    assert data.terrain_types[0].hex_color == "#aabbcc"
