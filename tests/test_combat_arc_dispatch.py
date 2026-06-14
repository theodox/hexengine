"""Arc-authoritative combat RPC dispatch (no legacy fallback when arc is declared)."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace

from games.hexdemo.combat import arc as combat_arc
from games.hexdemo.hooks import build_hooks

from hexengine.arcs import read_arc_cursor
from hexengine.hexes.types import Hex
from hexengine.hooks.title import TitleHooks
from hexengine.server.arcs import (
    CombatArcDispatch,
    begin_combat_arc,
    finish_combat_arc_dispatch,
    overlay_rpc_action_types,
    try_arc_move_unit,
    try_arc_rpc,
    try_combat_arc_move_unit,
    try_combat_arc_rpc,
)
from hexengine.state import ActionManager, GameState
from hexengine.state.game_state import UnitState

HOOKS = build_hooks()


class _Host:
    def __init__(self, state: GameState, hooks: TitleHooks = HOOKS) -> None:
        self.hooks = hooks
        self.action_manager = ActionManager(state)
        self.errors: list[str] = []
        self.sent = 0
        self.broadcasts = 0

    async def _send_error(self, player_id: str, message: str) -> None:
        self.errors.append(message)

    async def _send_message(self, player_id: str, message: object) -> None:
        self.sent += 1

    async def _broadcast_state_update(self) -> None:
        self.broadcasts += 1

    def movement_arc_spec(self):
        return None


def _player(faction: str) -> SimpleNamespace:
    return SimpleNamespace(faction=faction)


def _retreat_state() -> GameState:
    unit = UnitState(
        unit_id="u1", unit_type="inf", faction="union", position=Hex(0, 0, 0)
    )
    st = GameState.create_empty()
    st = st.with_board(st.board.with_unit(unit))
    st = st.with_turn(replace(st.turn, current_faction="union"))
    return st.with_session_state(
        {"retreat_obligations": {"u1": 1}},
        session_state_key="hexdemo",
    )


def test_try_arc_rpc_alias_delegates() -> None:
    host = _Host(_retreat_state(), hooks=TitleHooks())
    assert asyncio.run(
        try_combat_arc_rpc(host, "p1", _player("union"), "CombatAdvance")
    ) == asyncio.run(try_arc_rpc(host, "p1", _player("union"), "CombatAdvance"))


def test_overlay_rpc_action_types_from_declared_arc() -> None:
    from hexengine.server.arcs import overlay_rpc_action_types

    types = overlay_rpc_action_types(HOOKS)
    assert "CombatAdvance" in types
    assert "MoveUnit" not in types
    assert "Attack" not in types


def test_try_rpc_not_declared_without_combat_arc() -> None:
    host = _Host(_retreat_state(), hooks=TitleHooks())
    outcome = asyncio.run(
        try_combat_arc_rpc(host, "p1", _player("union"), "CombatAdvance")
    )
    assert outcome == CombatArcDispatch.NOT_DECLARED


def test_try_rpc_no_cursor_when_obligations_without_begin() -> None:
    host = _Host(_retreat_state())
    outcome = asyncio.run(
        try_combat_arc_rpc(
            host, "p1", _player("union"), "CombatDisruptInsteadOfRetreat"
        )
    )
    assert outcome == CombatArcDispatch.NO_CURSOR


def test_try_rpc_rejects_wrong_owner() -> None:
    host = _Host(_retreat_state())
    begin_combat_arc(host)
    outcome = asyncio.run(
        try_combat_arc_rpc(
            host, "p1", _player("rebel"), "CombatDisruptInsteadOfRetreat"
        )
    )
    assert outcome == CombatArcDispatch.REJECTED


def test_try_move_unit_retreat_without_cursor_is_inactive() -> None:
    host = _Host(_retreat_state())
    params = {
        "unit_id": "u1",
        "from_hex": {"i": 0, "j": 0, "k": 0},
        "to_hex": {"i": 1, "j": -1, "k": 0},
    }
    outcome = asyncio.run(
        try_combat_arc_move_unit(
            host,
            "p1",
            _player("union"),
            params,
            is_retreat_fulfillment=True,
            is_advance_fulfillment=False,
        )
    )
    assert outcome == CombatArcDispatch.NO_CURSOR


def test_try_move_unit_routine_not_declared_during_move_phase() -> None:
    host = _Host(_retreat_state())
    begin_combat_arc(host)
    # Simulate combat arc completed: routine cursor restored.
    from hexengine.arcs import SetArcCursor

    host.action_manager.execute(SetArcCursor(None))
    from hexengine.server.arcs import begin_routine_slot

    begin_routine_slot(host, host.action_manager.current_state.turn.schedule_index)
    params = {
        "unit_id": "u1",
        "from_hex": {"i": 0, "j": 0, "k": 0},
        "to_hex": {"i": 1, "j": -1, "k": 0},
    }
    outcome = asyncio.run(
        try_combat_arc_move_unit(
            host,
            "p1",
            _player("union"),
            params,
            is_retreat_fulfillment=False,
            is_advance_fulfillment=False,
        )
    )
    assert outcome == CombatArcDispatch.NOT_DECLARED


def test_finish_dispatch_sends_error_on_reject() -> None:
    host = _Host(_retreat_state())
    done = asyncio.run(
        finish_combat_arc_dispatch(host, "p1", CombatArcDispatch.REJECTED)
    )
    assert done is True
    assert host.errors


def test_try_rpc_handles_disrupt_on_active_gate() -> None:
    host = _Host(_retreat_state())
    hx = dict(host.action_manager.current_state.session_state)
    hx["disrupt_instead_offered"] = True
    host.action_manager.replace_state(
        host.action_manager.current_state.with_session_state(hx)
    )
    begin_combat_arc(host)
    assert (
        read_arc_cursor(host.action_manager.current_state).segment_id
        == combat_arc.SEG_RETREAT_OR_DISRUPT_GATE
    )
    outcome = asyncio.run(
        try_combat_arc_rpc(
            host, "p1", _player("union"), "CombatDisruptInsteadOfRetreat"
        )
    )
    assert outcome == CombatArcDispatch.HANDLED
    assert host.broadcasts == 1
    assert not engine_read_session_state_obligations(host)


def engine_read_session_state_obligations(host: _Host) -> bool:
    from hexengine.state.engine_session_state import engine_read_session_state

    ro = engine_read_session_state(host.action_manager.current_state, "hexdemo").get(
        "retreat_obligations"
    )
    return bool(ro)
