"""Tests for `GameData` TOML loading (`hexengine.gamedef.game_data_toml`)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from hexengine.gamedef.game_data import GameData
from hexengine.gamedef.game_data_toml import (
    game_data_from_mapping,
    load_game_data_for_pack_root,
    merged_gamedata_dict_from_manifest,
)


def test_game_data_from_mapping_roundtrip_fields() -> None:
    gd = game_data_from_mapping(
        {
            "gamedata_schema": 1,
            "max_active_units_per_hex": 2,
            "movement_budget_attribute_key": "speed",
            "session_state_key": "pack",
            "title_css_file": "x.css",
            "faction_display_names": {"a": "A"},
            "faction_css_classes": {"a": "cls-a"},
            "hex_highlight_ui": {
                "schema": 1,
                "move_hex_class": "mv",
                "unknown_key": "ignored",
            },
        }
    )
    assert gd.max_active_units_per_hex == 2
    assert gd.movement_budget_attribute_key == "speed"
    assert gd.session_state_key == "pack"
    assert gd.title_css_file == "x.css"
    assert gd.faction_display_names == {"a": "A"}
    assert gd.faction_css_classes == {"a": "cls-a"}
    assert gd.hex_highlight_ui == {"schema": 1, "move_hex_class": "mv"}


def test_game_data_from_mapping_rejects_unknown_schema() -> None:
    with pytest.raises(ValueError, match="Unsupported gamedata_schema"):
        game_data_from_mapping({"gamedata_schema": 2})


def test_merged_manifest_overrides_file(tmp_path: Path) -> None:
    root = tmp_path / "p"
    root.mkdir()
    (root / "resources").mkdir()
    (root / "resources" / "base.toml").write_text(
        textwrap.dedent(
            """
            max_active_units_per_hex = 1
            session_state_key = "from_file"

            [faction_display_names]
            u = "U"
            """
        ).strip(),
        encoding="utf-8",
    )
    manifest = {
        "gamedata": {
            "file": "resources/base.toml",
            "max_active_units_per_hex": 5,
            "faction_display_names": {"u": "Override"},
        }
    }
    merged = merged_gamedata_dict_from_manifest(root, manifest)
    gd = game_data_from_mapping(merged)
    assert gd.max_active_units_per_hex == 5
    assert gd.session_state_key == "from_file"
    assert gd.faction_display_names == {"u": "Override"}


def test_merged_missing_file_errors(tmp_path: Path) -> None:
    root = tmp_path / "p"
    root.mkdir()
    manifest = {"gamedata": {"file": "nope.toml"}}
    with pytest.raises(ValueError, match="gamedata.file"):
        merged_gamedata_dict_from_manifest(root, manifest)


def test_load_game_data_for_pack_root_hexdemo() -> None:
    repo = Path(__file__).resolve().parents[1]
    pack = repo / "games" / "hexdemo"
    gd = load_game_data_for_pack_root(pack)
    assert gd.max_active_units_per_hex == 3
    assert gd.session_state_key == "hexdemo"
    assert "union" in gd.faction_display_names
    assert gd.hex_highlight_ui.get("move_hex_class") == "hexdemo-move-hex"
    assert gd.shell_ui.get("advance_turn_button_label") == "End Phase"
    assert gd.shell_ui.get("attack_confirm_label") == "Confirm attack"
    assert gd.interaction_kind_styles.get("retreat") == "interaction-msg--retreat"


def test_load_pack_record_includes_game_data(tmp_path: Path) -> None:
    from hexengine.game_packs import registry

    registry.reset_game_pack_registry_for_tests()
    root = tmp_path / "minipack"
    (root / "scenarios" / "one").mkdir(parents=True)
    (root / "minipack_py").mkdir()
    (root / "minipack_py" / "__init__.py").write_text("", encoding="utf-8")
    (root / "minipack_py" / "engine_entry.py").write_text(
        textwrap.dedent(
            """
            from hexengine.gamedef.builtin import InterleavedTwoFactionGameDefinition

            def load_game_definition():
                return InterleavedTwoFactionGameDefinition()
            """
        ).strip(),
        encoding="utf-8",
    )
    (root / "hexengine_pack.toml").write_text(
        textwrap.dedent(
            """
            manifest_version = 1
            [pack]
            id = "minipack"
            title = "Mini"
            [python]
            path_add = "."
            entry_module = "minipack_py.engine_entry"
            entry_callable = "load_game_definition"
            """
        ).strip(),
        encoding="utf-8",
    )
    registry.discover_game_packs(force=True)
    scenario = root / "scenarios" / "one" / "scenario.toml"
    scenario.write_text("# s", encoding="utf-8")
    rec = registry.resolve_pack_for_scenario(scenario)
    assert rec.game_data == GameData.empty()
