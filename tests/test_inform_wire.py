"""INFORM lane resolution from current_segment (P4)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GAMES = str(REPO_ROOT / "games")
SRC = str(REPO_ROOT / "src")
for p in (GAMES, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from hexengine.arcs.inform_wire import resolve_inform_lane
from hexengine.hooks.inform_popup import (
    InformPopupContext,
    default_inform_popup_for_viewer,
)
from hexengine.server.game_server import GameServer
from hexengine.state import GameState
from hexengine.state.game_state import TurnState


def test_resolve_inform_lane_prefers_client_kind() -> None:
    from games.hexdemo.game_config import (
        default_match_config,
        game_definition_from_config,
    )

    st = GameState.create_empty().with_turn(TurnState("union", "Combat", 2, 1, 1, 0))
    host = GameServer(
        st, game_definition=game_definition_from_config(default_match_config())
    )
    lane = resolve_inform_lane(
        host, st, viewer_faction="union", client_inform_kind="attack_plan"
    )
    assert lane.inform_kind == "attack_plan"
    assert lane.inform_profile == "attack_plan"


def test_resolve_inform_lane_from_segment_profile() -> None:
    from games.hexdemo.game_config import (
        default_match_config,
        game_definition_from_config,
    )

    st = GameState.create_empty().with_turn(TurnState("union", "Combat", 2, 1, 1, 0))
    server = GameServer(
        st, game_definition=game_definition_from_config(default_match_config())
    )
    lane = resolve_inform_lane(server, server.game_state, viewer_faction="union")
    assert lane.inform_kind == "attack_plan"
    assert lane.inform_profile == "attack_plan"
    assert lane.segment_kind == "combat"


def test_default_inform_popup_uses_profile_shell_key() -> None:
    ctx = InformPopupContext(
        state=GameState.create_empty(),
        viewer_faction="union",
        inform_kind="attack_plan",
        reason="no_attackable_enemy",
        anchor_hex=None,
        unit_id=None,
        shell_ui={"attack_plan_no_attackable_enemy": "Custom copy."},
        inform_profile="attack_plan",
        segment_kind="combat",
    )
    pm = default_inform_popup_for_viewer(ctx)
    assert pm.text == "Custom copy."
