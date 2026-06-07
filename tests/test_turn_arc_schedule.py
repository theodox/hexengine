"""Turn arc schedule declaration and server wiring (composable arcs, Phase 4)."""

from __future__ import annotations

from games.hexdemo.game_config import default_match_config, game_definition_from_config
from games.hexdemo.hooks import build_hooks
from games.hexdemo.turn_arc_schedule import (
    build_hexdemo_turn_arc_registry,
    hexdemo_schedule_slots,
)

from hexengine.arcs import read_arc_cursor
from hexengine.authoring.patterns import ROUTINE_SEGMENT
from hexengine.server import GameServer
from hexengine.server.arcs import schedule_next_phase_info
from hexengine.state import GameState
from hexengine.state.game_state import TurnState


def test_hexdemo_schedule_matches_four_phase_rota() -> None:
    reg = build_hexdemo_turn_arc_registry()
    entries = reg.schedule.turn_order_entries()
    assert len(entries) == 4
    assert entries[0]["phase"] == "Move"
    assert entries[1]["phase"] == "Combat"
    assert entries[2]["faction"] != entries[0]["faction"]
    assert entries[2]["phase"] == "Move"


def test_schedule_next_slot_wraps() -> None:
    reg = build_hexdemo_turn_arc_registry()
    slot, idx = reg.schedule.next_after(3)
    assert idx == 0
    assert slot.phase == "Move"
    assert slot.faction == hexdemo_schedule_slots()[0].faction


def test_routine_specs_cover_all_slots() -> None:
    reg = build_hexdemo_turn_arc_registry()
    for slot in reg.schedule.slots:
        assert slot.routine_arc_id in reg.routine_specs
        arc = reg.routine_specs[slot.routine_arc_id].arc
        assert arc.entry == ROUTINE_SEGMENT
        seg = arc.get(ROUTINE_SEGMENT)
        if slot.phase == "Move":
            assert "MoveUnit" in seg.allowed_actions
        if slot.phase == "Combat":
            assert "Attack" in seg.allowed_actions


class _ScheduleHost:
    def __init__(self, state: GameState) -> None:
        from hexengine.state.action_manager import ActionManager

        self.hooks = build_hooks()
        self.action_manager = ActionManager(state)

    def turn_arc_registry(self):
        return build_hexdemo_turn_arc_registry()


def test_schedule_next_phase_info_from_registry() -> None:
    st = GameState.create_empty().with_turn(TurnState("union", "Move", 4, 1, 0, 0))
    host = _ScheduleHost(st)
    info = schedule_next_phase_info(host)
    assert info is not None
    assert info["phase"] == "Combat"
    assert info["schedule_index"] == 1


def test_server_begins_routine_cursor_on_init() -> None:
    gd = game_definition_from_config(default_match_config())
    st = GameState.create_empty().with_turn(TurnState("union", "Move", 4, 1, 0, 0))
    server = GameServer(st, game_definition=gd)
    cur = read_arc_cursor(server.game_state)
    assert cur is not None
    assert cur.arc_id == "union_move"
    assert cur.segment_id == ROUTINE_SEGMENT
