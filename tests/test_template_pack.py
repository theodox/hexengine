"""Template title pack (games/template) — authoring patterns smoke test."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_SCENARIO = (
    REPO_ROOT / "games" / "template" / "scenarios" / "default" / "scenario.toml"
)


def test_template_pack_is_discoverable() -> None:
    from hexengine.game_packs import registry

    registry.discover_game_packs(force=True)
    ids = {rec.manifest.pack_id for rec in registry.registered_packs()}
    assert "template" in ids


def test_template_manifest_loads_game_data() -> None:
    from hexengine.game_packs.registry import resolve_pack_for_scenario

    rec = resolve_pack_for_scenario(TEMPLATE_SCENARIO)
    assert rec.manifest.pack_id == "template"
    assert rec.game_data.faction_display_names["blue"] == "Blue"


def test_template_turn_arc_registry() -> None:
    from games.template.turn_arc_schedule import build_template_turn_arc_registry

    reg = build_template_turn_arc_registry()
    entries = reg.schedule.turn_order_entries()
    assert len(entries) == 2
    assert entries[0] == {"faction": "blue", "phase": "Move", "max_actions": 4}
    assert entries[1] == {"faction": "red", "phase": "Move", "max_actions": 4}
    assert "blue_move" in reg.routine_specs


def test_template_validate_title_contract() -> None:
    from games.template.registry import build_game_definition

    from hexengine.hooks.internal.contracts import validate_title_contract

    validate_title_contract(build_game_definition())


def test_template_combat_scaffold_binding() -> None:
    from games.template.combat_arc import build_template_combat_arc_spec

    spec = build_template_combat_arc_spec()
    spec.arc.validate()


def test_template_server_begins_routine_cursor() -> None:
    from games.template.game_config import (
        default_match_config,
        game_definition_from_config,
    )

    from hexengine.arcs import read_arc_cursor
    from hexengine.server import GameServer
    from hexengine.state import GameState
    from hexengine.state.game_state import TurnState

    gd = game_definition_from_config(default_match_config())
    st = GameState.create_empty().with_turn(TurnState("blue", "Move", 4, 1, 0, 0))
    server = GameServer(st, game_definition=gd)
    cursor = read_arc_cursor(server.action_manager.current_state)
    assert cursor is not None
    assert cursor.arc_id == "blue_move"
    assert cursor.segment_id == "routine"
