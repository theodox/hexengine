"""Gate-string catalog defaults removed — segment projection is authoritative."""

from __future__ import annotations

from games.hexdemo import combat_transitions
from games.hexdemo.game_config import default_match_config, game_definition_from_config

from hexengine.arcs import ArcCursor, with_arc_cursor
from hexengine.server import GameServer
from hexengine.state import GameState
from hexengine.state.game_state import TurnState


def test_registry_title_ignores_stale_legacy_combat_gate_on_routine() -> None:
    gd = game_definition_from_config(default_match_config())
    st = GameState.create_empty().with_turn(TurnState("union", "Move", 4, 1, 0, 0))
    st = st.with_title_state(
        {"combat_gate": combat_transitions.GATE_AWAITING_ADVANCE},
        title_bucket_key="hexdemo",
    )
    st = with_arc_cursor(st, ArcCursor(arc_id="union_move", segment_id="routine"))
    server = GameServer(st, game_definition=gd)
    assert server._resolve_blocks_routine_phase_advance(st) is False


def test_registry_title_blocks_next_phase_on_combat_segment() -> None:
    gd = game_definition_from_config(default_match_config())
    st = GameState.create_empty().with_turn(TurnState("union", "Combat", 2, 1, 1, 0))
    st = st.with_title_state({}, title_bucket_key="hexdemo")
    st = with_arc_cursor(st, ArcCursor(arc_id="combat", segment_id="retreat_gate"))
    server = GameServer(st, game_definition=gd)
    assert server._resolve_blocks_routine_phase_advance(st) is True
