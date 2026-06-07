"""
Phase 2c: retreat-fulfillment MoveUnit through the generic arc runner.

Covers the title ``apply_retreat_step`` effect, stacked retreats, cursor advancement
through the auto ``resolve`` segment, and arc-only dispatch when a combat arc is declared.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace

from games.hexdemo import combat_actions, combat_arc, combat_transitions
from games.hexdemo.hooks import build_hooks

from hexengine.arcs import read_arc_cursor
from hexengine.hexes.types import Hex
from hexengine.server.arcs import begin_combat_arc, drive_combat_arc_event
from hexengine.state import ActionManager, GameState
from hexengine.state.game_state import UnitState
from hexengine.state.title_extension import title_bucket

HOOKS = build_hooks()


class _Host:
    def __init__(self, state: GameState) -> None:
        self.hooks = HOOKS
        self.action_manager = ActionManager(state)
        self.broadcasts = 0

    async def _send_message(self, player_id: str, message: object) -> None:
        pass

    async def _broadcast_state_update(self) -> None:
        self.broadcasts += 1


def _player(faction: str) -> SimpleNamespace:
    return SimpleNamespace(faction=faction)


def _state_with_stack(
    *,
    gate: str,
    obligations: dict[str, int],
    units: dict[str, tuple[str, Hex]],
    current: str = "union",
) -> GameState:
    st = GameState.create_empty()
    board = st.board
    for uid, (faction, pos) in units.items():
        board = board.with_unit(
            UnitState(unit_id=uid, unit_type="inf", faction=faction, position=pos)
        )
    st = st.with_board(board)
    st = st.with_turn(replace(st.turn, current_faction=current))
    bucket: dict = {"retreat_obligations": obligations}
    if gate == combat_transitions.GATE_AWAITING_RETREAT_OR_DISRUPT:
        bucket["disrupt_instead_offered"] = True
    return st.with_title_state(bucket, title_bucket_key="hexdemo")


def test_apply_retreat_step_moves_primary_and_clears_obligation() -> None:
    h0, h1 = Hex(0, 0, 0), Hex(1, -1, 0)
    st = _state_with_stack(
        gate=combat_transitions.GATE_AWAITING_RETREAT,
        obligations={"u1": 1},
        units={"u1": ("union", h0)},
    )
    params = {
        "unit_id": "u1",
        "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
        "to_hex": {"i": h1.i, "j": h1.j, "k": h1.k},
    }
    actions = combat_actions.apply_retreat_fulfillment_step(
        st, "hexdemo", "union", params
    )
    mgr = ActionManager(st)
    for a in actions:
        mgr.execute(a)
    final = mgr.current_state
    assert final.board.units["u1"].position == h1
    hx = title_bucket(final, "hexdemo")
    assert "u1" not in (hx.get("retreat_obligations") or {})


def test_apply_retreat_step_moves_stacked_units() -> None:
    h0, h1 = Hex(0, 0, 0), Hex(1, -1, 0)
    st = _state_with_stack(
        gate=combat_transitions.GATE_AWAITING_RETREAT,
        obligations={"u1": 1, "u2": 1},
        units={"u1": ("union", h0), "u2": ("union", h0)},
    )
    params = {
        "unit_id": "u1",
        "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
        "to_hex": {"i": h1.i, "j": h1.j, "k": h1.k},
    }
    mgr = ActionManager(st)
    for a in combat_actions.apply_retreat_fulfillment_step(
        st, "hexdemo", "union", params
    ):
        mgr.execute(a)
    final = mgr.current_state
    assert final.board.units["u1"].position == h1
    assert final.board.units["u2"].position == h1
    hx = title_bucket(final, "hexdemo")
    assert not hx.get("retreat_obligations")


def test_retreat_through_runner_advances_cursor_to_resolve() -> None:
    h0, h1 = Hex(0, 0, 0), Hex(1, -1, 0)
    host = _Host(
        _state_with_stack(
            gate=combat_transitions.GATE_AWAITING_RETREAT,
            obligations={"u1": 1},
            units={"u1": ("union", h0)},
        )
    )
    begin_combat_arc(host)
    assert read_arc_cursor(host.action_manager.current_state).segment_id == (
        combat_arc.SEG_RETREAT_GATE
    )

    params = {
        "unit_id": "u1",
        "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
        "to_hex": {"i": h1.i, "j": h1.j, "k": h1.k},
    }
    handled = asyncio.run(
        drive_combat_arc_event(host, "p1", _player("union"), "MoveUnit", params)
    )

    assert handled is True
    assert host.broadcasts == 1
    final = host.action_manager.current_state
    assert final.board.units["u1"].position == h1
    cur = read_arc_cursor(final)
    assert cur is None or cur.arc_id != "combat"  # routine cursor restored (Phase 4)


def test_partial_retreat_loops_cursor_to_retreat_gate() -> None:
    """When one of two obligated units retreats, resolve loops back to retreat_gate."""

    h0, h1, h2 = Hex(0, 0, 0), Hex(1, -1, 0), Hex(2, -2, 0)
    host = _Host(
        _state_with_stack(
            gate=combat_transitions.GATE_AWAITING_RETREAT,
            obligations={"u1": 1, "u2": 1},
            units={"u1": ("union", h0), "u2": ("union", h2)},
            current="rebel",
        )
    )
    begin_combat_arc(host)
    params = {
        "unit_id": "u1",
        "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
        "to_hex": {"i": h1.i, "j": h1.j, "k": h1.k},
    }
    handled = asyncio.run(
        drive_combat_arc_event(host, "p1", _player("union"), "MoveUnit", params)
    )
    assert handled is True
    final = host.action_manager.current_state
    assert final.board.units["u1"].position == h1
    assert final.board.units["u2"].position == h2
    hx = title_bucket(final, "hexdemo")
    assert hx.get("retreat_obligations") == {"u2": 1}
    cur = read_arc_cursor(final)
    assert cur is not None
    assert cur.segment_id == combat_arc.SEG_RETREAT_GATE


def test_retreat_without_cursor_rejected() -> None:
    h0, h1 = Hex(0, 0, 0), Hex(1, -1, 0)
    host = _Host(
        _state_with_stack(
            gate=combat_transitions.GATE_AWAITING_RETREAT,
            obligations={"u1": 1},
            units={"u1": ("union", h0)},
        )
    )
    params = {
        "unit_id": "u1",
        "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
        "to_hex": {"i": h1.i, "j": h1.j, "k": h1.k},
    }
    handled = asyncio.run(
        drive_combat_arc_event(host, "p1", _player("union"), "MoveUnit", params)
    )
    assert handled is False
    assert host.action_manager.current_state.board.units["u1"].position == h0


def test_apply_retreat_step_skips_primary_already_at_destination() -> None:
    """Stepwise path completion: primary moved incrementally, stackmate still at origin."""

    h0, h1 = Hex(0, 0, 0), Hex(1, -1, 0)
    st = _state_with_stack(
        gate=combat_transitions.GATE_AWAITING_RETREAT,
        obligations={"u1": 2, "u2": 2},
        units={"u1": ("union", h1), "u2": ("union", h0)},
    )
    params = {
        "unit_id": "u1",
        "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
        "to_hex": {"i": h1.i, "j": h1.j, "k": h1.k},
    }
    mgr = ActionManager(st)
    for a in combat_actions.apply_retreat_fulfillment_step(
        st, "hexdemo", "union", params
    ):
        mgr.execute(a)
    final = mgr.current_state
    assert final.board.units["u1"].position == h1
    assert final.board.units["u2"].position == h1
    assert not title_bucket(final, "hexdemo").get("retreat_obligations")


def test_retreat_or_disrupt_gate_accepts_moveunit() -> None:
    h0, h1 = Hex(0, 0, 0), Hex(1, -1, 0)
    host = _Host(
        _state_with_stack(
            gate=combat_transitions.GATE_AWAITING_RETREAT_OR_DISRUPT,
            obligations={"u1": 1},
            units={"u1": ("union", h0)},
        )
    )
    begin_combat_arc(host)
    cur = read_arc_cursor(host.action_manager.current_state)
    assert cur.segment_id == combat_arc.SEG_RETREAT_OR_DISRUPT_GATE

    params = {
        "unit_id": "u1",
        "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
        "to_hex": {"i": h1.i, "j": h1.j, "k": h1.k},
    }
    assert asyncio.run(
        drive_combat_arc_event(host, "p1", _player("union"), "MoveUnit", params)
    )
    assert host.action_manager.current_state.board.units["u1"].position == h1


def test_wrong_owner_retreat_move_rejected() -> None:
    h0, h1 = Hex(0, 0, 0), Hex(1, -1, 0)
    host = _Host(
        _state_with_stack(
            gate=combat_transitions.GATE_AWAITING_RETREAT,
            obligations={"u1": 1},
            units={"u1": ("union", h0)},
        )
    )
    begin_combat_arc(host)
    params = {
        "unit_id": "u1",
        "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
        "to_hex": {"i": h1.i, "j": h1.j, "k": h1.k},
    }
    handled = asyncio.run(
        drive_combat_arc_event(host, "p1", _player("rebel"), "MoveUnit", params)
    )
    assert handled is False
    assert host.action_manager.current_state.board.units["u1"].position == h0
