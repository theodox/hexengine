"""Hexdemo pack layout, gameroot helpers, and boot banner."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HEXDEMO_SCENARIO = (
    REPO_ROOT / "games" / "hexdemo" / "scenarios" / "default" / "scenario.toml"
)


def test_display_faction_name_hexdemo() -> None:
    from hexengine.gamedef.faction_display import (
        display_faction_name,
        display_phase_name,
    )

    assert display_faction_name("confederate") == "Confederate"
    assert display_faction_name("union") == "Union"
    assert display_faction_name("red") == "Red"
    assert display_phase_name("attack") == "Attack"
    assert display_phase_name("Movement") == "Movement"


def test_scenario_path_indicates_hexdemo_pack() -> None:
    from hexengine.gameroot import scenario_path_indicates_hexdemo_pack

    assert scenario_path_indicates_hexdemo_pack(HEXDEMO_SCENARIO)
    assert not scenario_path_indicates_hexdemo_pack(
        REPO_ROOT
        / "src"
        / "hexengine"
        / "scenarios"
        / "data"
        / "test_scenario"
        / "scenario.toml"
    )


def test_try_hexdemo_loaded_banner_once(caplog: pytest.LogCaptureFixture) -> None:
    from hexengine.gameroot import (
        reset_hexdemo_loaded_banner_for_tests,
        try_hexdemo_loaded_banner,
    )

    reset_hexdemo_loaded_banner_for_tests()
    with caplog.at_level(logging.INFO, logger="hexdemo.boot"):
        try_hexdemo_loaded_banner(HEXDEMO_SCENARIO)
        try_hexdemo_loaded_banner(HEXDEMO_SCENARIO)

    boot_logs = [r for r in caplog.records if r.name == "hexdemo.boot"]
    assert len(boot_logs) == 1
    assert boot_logs[0].levelname == "INFO"
    assert boot_logs[0].message == "welcome to hexdemo"


def test_load_game_definition_for_hexdemo_scenario() -> None:
    from hexengine.gameroot import (
        initial_faction_for_game_definition,
        load_game_definition_for_scenario,
    )

    gd = load_game_definition_for_scenario(HEXDEMO_SCENARIO)
    assert gd.available_factions() == ["union", "confederate"]
    assert initial_faction_for_game_definition(gd) == "union"


def test_load_game_definition_for_scenario_rejects_engine_packaged_path() -> None:
    from hexengine.gameroot import load_game_definition_for_scenario
    from hexengine.scenarios.load.parse import default_scenario_path

    with pytest.raises(ValueError, match="No title rules"):
        load_game_definition_for_scenario(default_scenario_path())


def test_hexdemo_registry_build() -> None:
    import sys

    games = str(REPO_ROOT / "games")
    if games not in sys.path:
        sys.path.insert(0, games)
    from hexdemo.registry import build_game_definition, registered_game_definition_ids

    gd = build_game_definition("interleaved")
    assert gd.available_factions() == ["union", "confederate"]
    assert "default" in registered_game_definition_ids()


def test_hexdemo_default_turn_order_four_phases() -> None:
    """Default / interleaved registry uses Union then Confederate Move/Combat."""
    import sys

    games = str(REPO_ROOT / "games")
    if games not in sys.path:
        sys.path.insert(0, games)
    from hexdemo.registry import build_game_definition

    gd = build_game_definition("default")
    order = gd.turn_order()
    assert len(order) == 4
    assert order[0] == {"faction": "union", "phase": "Move", "max_actions": 2}
    assert order[1] == {"faction": "union", "phase": "Combat", "max_actions": 2}
    assert order[2] == {"faction": "confederate", "phase": "Move", "max_actions": 2}
    assert order[3] == {"faction": "confederate", "phase": "Combat", "max_actions": 2}


def test_hexdemo_game_config_matches_registry() -> None:
    """Registry ids must match `hexdemo.game_config.HexdemoMatchConfig` defaults."""
    import sys

    games = str(REPO_ROOT / "games")
    if games not in sys.path:
        sys.path.insert(0, games)
    from hexdemo.game_config import HexdemoMatchConfig, game_definition_from_config
    from hexdemo.registry import build_game_definition

    for key in ("interleaved", "sequential"):
        reg = build_game_definition(key)
        cfg = game_definition_from_config(HexdemoMatchConfig.from_registry_key(key))
        assert type(reg) is type(cfg)
        assert reg.turn_order() == cfg.turn_order()

    default_gd = build_game_definition("default")
    inter_gd = build_game_definition("interleaved")
    assert type(default_gd) is type(inter_gd)
    assert default_gd.turn_order() == inter_gd.turn_order()
