"""Segment projection is authoritative for routine phase-advance blocking."""

from __future__ import annotations

from games.hexdemo.game_config import default_match_config, game_definition_from_config

from hexengine.arcs import ArcCursor, with_arc_cursor
from hexengine.server import GameServer
from hexengine.state import GameState
from hexengine.state.game_state import TurnState


def test_registry_title_blocks_next_phase_on_combat_segment() -> None:
    gd = game_definition_from_config(default_match_config())
    st = GameState.create_empty().with_turn(TurnState("union", "Combat", 2, 1, 1, 0))
    st = st.with_session_state({}, session_state_key="hexdemo")
    st = with_arc_cursor(st, ArcCursor(arc_id="combat", segment_id="retreat_gate"))
    server = GameServer(st, game_definition=gd)
    assert server._resolve_blocks_routine_phase_advance(st) is True
