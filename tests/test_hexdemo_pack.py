"""Hexdemo pack layout, gameroot helpers, and boot banner."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HEXDEMO_SCENARIO = (
    REPO_ROOT / "games" / "hexdemo" / "scenarios" / "default" / "scenario.toml"
)


def test_hexdemo_faction_display_names_in_game_data() -> None:
    from hexengine.gamedef.game_data_toml import load_game_data_for_pack_root

    root = REPO_ROOT / "games" / "hexdemo"
    gd = load_game_data_for_pack_root(root)
    assert gd.faction_display_names["union"] == "Union"
    assert gd.faction_display_names["confederate"] == "Confederate"


def test_hexdemo_manifest_declares_title_load_hooks() -> None:
    from hexengine.game_packs.registry import resolve_pack_for_scenario
    from hexengine.game_packs.resources import read_pack_resource_text

    rec = resolve_pack_for_scenario(HEXDEMO_SCENARIO)
    tl = rec.manifest.hooks_title_load
    assert tl is not None
    assert tl.module == "hexdemo.hooks.title_load"
    assert tl.splash_html == "splash.html"
    assert tl.splash_callable == "present_splash"
    assert tl.setup_callable == "run_setup"
    splash = read_pack_resource_text(rec.root, tl.splash_html)
    assert splash is not None
    assert "Hexdemo" in splash
    assert rec.game_data.max_active_units_per_hex == 3
    assert rec.game_data.title_state_extension_key == "hexdemo"


def test_try_pack_title_load_server_no_hook_is_safe() -> None:
    from hexengine.gameroot import (
        reset_title_load_hooks_for_tests,
        try_pack_title_load_server,
    )

    reset_title_load_hooks_for_tests()
    try_pack_title_load_server(HEXDEMO_SCENARIO)
    try_pack_title_load_server(HEXDEMO_SCENARIO)


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

    with pytest.raises(ValueError, match="No registered game pack"):
        load_game_definition_for_scenario(default_scenario_path())


def test_hexdemo_registry_build() -> None:
    import sys

    games = str(REPO_ROOT / "games")
    if games not in sys.path:
        sys.path.insert(0, games)
    from hexdemo.registry import build_game_definition

    gd = build_game_definition()
    assert gd.available_factions() == ["union", "confederate"]


def test_hexdemo_default_turn_order_four_phases() -> None:
    """Shipped hexdemo uses Union then Confederate Move/Combat (4 moves / 2 combats per segment)."""
    import sys

    games = str(REPO_ROOT / "games")
    if games not in sys.path:
        sys.path.insert(0, games)
    from hexdemo.registry import build_game_definition

    gd = build_game_definition()
    order = gd.turn_order()
    assert len(order) == 4
    assert order[0] == {"faction": "union", "phase": "Move", "max_actions": 4}
    assert order[1] == {"faction": "union", "phase": "Combat", "max_actions": 2}
    assert order[2] == {"faction": "confederate", "phase": "Move", "max_actions": 4}
    assert order[3] == {"faction": "confederate", "phase": "Combat", "max_actions": 2}


def test_hexdemo_game_config_matches_registry() -> None:
    """`build_game_definition` matches `game_definition_from_config(default_match_config())`."""
    import sys

    games = str(REPO_ROOT / "games")
    if games not in sys.path:
        sys.path.insert(0, games)
    from hexdemo.game_config import default_match_config, game_definition_from_config
    from hexdemo.registry import build_game_definition

    reg = build_game_definition()
    cfg = game_definition_from_config(default_match_config())
    assert type(reg) is type(cfg)
    assert reg.turn_order() == cfg.turn_order()


def _ensure_games_on_path() -> None:
    import sys

    games = str(REPO_ROOT / "games")
    if games not in sys.path:
        sys.path.insert(0, games)


def test_hexdemo_focus_unit_after_sync() -> None:
    _ensure_games_on_path()
    from hexdemo.focus import focus_unit_id_after_state_sync
    from hexengine.hexes.types import Hex
    from hexengine.state import GameState
    from hexengine.state.game_state import BoardState, TurnState, UnitState

    h0 = Hex(0, 0, 0)
    board = BoardState(
        units={
            "only": UnitState(
                unit_id="only",
                unit_type="inf",
                faction="union",
                position=h0,
                health=100,
                active=True,
            ),
        }
    )
    turn = TurnState(
        current_faction="union",
        current_phase="Move",
        phase_actions_remaining=2,
        turn_number=1,
        schedule_index=0,
    )
    st = GameState(
        board=board,
        turn=turn,
        title_state={"retreat_obligations": {"only": 1}},
        title_bucket_key="hexdemo",
        rng_log=(),
    )
    assert focus_unit_id_after_state_sync(st, "union") == "only"
    assert focus_unit_id_after_state_sync(st, "confederate") is None
    assert focus_unit_id_after_state_sync(st, None) is None
