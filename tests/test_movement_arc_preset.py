"""Movement arc opt-in preset (charter phase 5)."""

from __future__ import annotations

from hexengine.gamedef.game_data import GameData
from hexengine.hooks.arcs import ArcsHooks
from hexengine.hooks.core import ENGINE_MOVEMENT_ARC_PRESET
from hexengine.hooks.title import TitleHooks
from hexengine.server import GameServer
from hexengine.state import GameState
from hexengine.state.game_state import TurnState


def test_template_server_has_no_movement_arc_spec() -> None:
    from games.template.game_config import (
        default_match_config,
        game_definition_from_config,
    )

    gd = game_definition_from_config(default_match_config())
    st = GameState.create_empty().with_turn(TurnState("blue", "Move", 4, 1, 0, 0))
    server = GameServer(st, game_definition=gd)
    assert server.movement_arc_spec() is None


def test_movement_arc_preset_requires_explicit_hook() -> None:
    class NoMovementArc:
        hooks = TitleHooks()

        @property
        def game_data(self) -> GameData:
            return GameData.empty()

        def turn_order(self):
            return []

    st = GameState.create_empty()
    server = GameServer(st, game_definition=NoMovementArc())
    assert server.movement_arc_spec() is None


def test_hexdemo_binds_movement_arc_preset() -> None:
    from games.hexdemo.hooks import build_hooks

    assert build_hooks().arcs.movement_arc_spec() is ENGINE_MOVEMENT_ARC_PRESET


def test_movement_arc_preset_builds_spec_on_server() -> None:
    class PresetTitle:
        hooks = TitleHooks(
            arcs=ArcsHooks(movement_arc=lambda: ENGINE_MOVEMENT_ARC_PRESET),
        )

        @property
        def game_data(self) -> GameData:
            return GameData.empty()

        def turn_order(self):
            return []

    st = GameState.create_empty()
    server = GameServer(st, game_definition=PresetTitle())
    spec = server.movement_arc_spec()
    assert spec is not None
    assert spec.arc.id == "movement"
    spec.arc.validate()
