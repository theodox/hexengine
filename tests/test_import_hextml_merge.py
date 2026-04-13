"""Tests for tools/import_hextml_map.py merge / terrain overlay helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_MOD_PATH = _ROOT / "tools" / "import_hextml_map.py"
_spec = importlib.util.spec_from_file_location("import_hextml_map", _MOD_PATH)
assert _spec and _spec.loader
_im = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_im)


def test_split_scenario_for_map_replace() -> None:
    text = (
        "# h\n\n"
        'name = "N"\n'
        'description = "D"\n\n'
        "[map]\n"
        "hex_size = 24\n\n"
        "[[terrain_groups]]\n"
        'terrain = "plain"\n'
        "movement_cost = 1.0\n"
        "positions = []\n\n"
        "[[unit_placements]]\n"
        "type = x\n"
        "positions = []\n"
    )
    head, tail = _im._split_scenario_for_map_replace(text)
    assert 'name = "N"' in head
    assert "[map]" not in head
    assert tail.startswith("[[unit_placements]]")
    assert "[[terrain_groups]]" not in tail


def test_merged_terrain_stats_overlay_wins() -> None:
    overlay = {
        "plain": {
            "movement_cost": 9.0,
            "block_los": True,
            "hex_color": "#111111",
        }
    }
    s = _im._merged_terrain_stats("plain", overlay)
    assert s["movement_cost"] == 9.0
    assert s["block_los"] is True
    assert s["hex_color"] == "#111111"


def test_merged_terrain_stats_new_terrain_default_block_los_false() -> None:
    s = _im._merged_terrain_stats("brand-new-terrain", None)
    assert s["block_los"] is False


def test_strip_terrain_groups_from_tail_removes_stray_after_unit_placements() -> None:
    tail = (
        "[[unit_graphics]]\n"
        "type = x\n\n"
        "[[unit_placements]]\n"
        "positions = []\n\n"
        "[[terrain_groups]]\n"
        'terrain = "plain"\n'
        "movement_cost = 1.0\n"
        "positions = [\n"
        "  { position = [0, 0] },\n"
        "]\n"
    )
    cleaned = _im._strip_terrain_groups_from_tail(tail)
    assert "[[terrain_groups]]" not in cleaned
    assert "[[unit_graphics]]" in cleaned
    assert "[[unit_placements]]" in cleaned
