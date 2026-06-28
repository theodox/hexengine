"""Phase 2d: obligation clear and advance moves without combat_gate mirror."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace

from games.hexdemo.combat import actions as combat_actions, arc as combat_arc
from games.hexdemo.hooks import build_hooks

from hexengine.arcs import ArcCursor, SetArcCursor, read_arc_cursor, with_arc_cursor
from hexengine.arcs.movement_arc_decl import MOVEMENT_ARC_ID
from hexengine.authoring.patterns.combat import SEG_ADVANCE_GATE, SEG_RESOLVE
from hexengine.hexes.math import neighbors
from hexengine.hexes.types import Hex
from hexengine.server.arcs import (
    drive_overlay_arc_event,
    resume_combat_arc_after_retreat_fulfillment,
)
from hexengine.server.arcs.movement_arc_effects import build_retreat_fulfillment_flow
from hexengine.state import ActionManager, GameState
from hexengine.state.game_state import BoardState, TurnState, UnitState
from hexengine.state.movement_arc import HEXENGINE_MOVEMENT_ARC_KEY
from hexengine.state.engine_session_state import engine_read_session_state


def test_clear_unit_retreat_obligation_does_not_touch_segment_state() -> None:
    st = GameState.create_empty().with_session_state(
        {"retreat_obligations": {"u1": 1}},
        session_state_key="hexdemo",
    )
    patch = combat_actions.patch_clear_retreat_obligations(st, "hexdemo", ("u1",))
    assert patch is not None
    mgr = ActionManager(st)
    mgr.execute(patch)
    hx = engine_read_session_state(mgr.current_state, "hexdemo")
    assert not hx.get("retreat_obligations")
    assert "combat_gate" not in hx


def test_apply_retreat_fulfillment_clears_obligations_when_done() -> None:
    h0, h1 = Hex(0, 0, 0), Hex(1, -1, 0)
    st = GameState.create_empty()
    st = st.with_board(
        st.board.with_unit(
            UnitState(unit_id="u1", unit_type="inf", faction="union", position=h0)
        )
    )
    st = st.with_session_state(
        {"retreat_obligations": {"u1": 1}},
        session_state_key="hexdemo",
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
    hx = engine_read_session_state(mgr.current_state, "hexdemo")
    assert not hx.get("retreat_obligations")


class _Host:
    def __init__(self, state: GameState) -> None:
        self.hooks = build_hooks()
        self.action_manager = ActionManager(state)
        self.broadcasts = 0

    async def _send_message(self, player_id: str, message: object) -> None:
        pass

    async def _broadcast_state_update(self) -> None:
        self.broadcasts += 1


def test_advance_moveunit_through_runner() -> None:
    h0, h1 = Hex(0, 0, 0), Hex(1, -1, 0)
    st = GameState.create_empty()
    st = st.with_board(
        st.board.with_unit(
            UnitState(unit_id="u_att", unit_type="inf", faction="union", position=h0)
        )
    )
    st = st.with_turn(replace(st.turn, current_faction="union"))
    st = st.with_session_state(
        {
            "advance": {
                "faction": "union",
                "attacker_id": "u_att",
                "unit_ids": ["u_att"],
                "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
                "to_hex": {"i": h1.i, "j": h1.j, "k": h1.k},
            },
        },
        session_state_key="hexdemo",
    )
    host = _Host(st)
    host.action_manager.execute(
        SetArcCursor(ArcCursor(arc_id="combat", segment_id=combat_arc.SEG_ADVANCE_GATE))
    )
    cur = read_arc_cursor(host.action_manager.current_state)
    assert cur is not None
    assert cur.segment_id == "advance_gate"

    params = {
        "unit_id": "u_att",
        "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
        "to_hex": {"i": h1.i, "j": h1.j, "k": h1.k},
    }
    handled = asyncio.run(
        drive_overlay_arc_event(
            host, "p1", SimpleNamespace(faction="union"), "MoveUnit", params
        )
    )
    assert handled is True
    final = host.action_manager.current_state
    assert final.board.units["u_att"].position == h1
    cur = read_arc_cursor(final)
    assert cur is None or cur.arc_id != "combat"
    hx = engine_read_session_state(final, "hexdemo")
    assert "advance" not in hx


def test_resume_combat_arc_after_movement_retreat_opens_advance_gate() -> None:
    """Movement-arc retreat fulfillment must re-enter combat ``resolve`` for advance."""
    h_att = Hex(0, 0, 0)
    h_def = Hex(1, -1, 0)
    h_ret = next(h for h in neighbors(h_def) if h != h_att)

    board = BoardState(
        units={
            "u_att": UnitState(
                unit_id="u_att",
                unit_type="inf",
                faction="union",
                position=h_att,
                active=True,
            ),
            "u_def": UnitState(
                unit_id="u_def",
                unit_type="inf",
                faction="confederate",
                position=h_ret,
                active=True,
            ),
        }
    )
    session = {
        "last_combat": {
            "outcome": "defender_retreat",
            "attacker_id": "u_att",
            "attacker_ids": ["u_att"],
            "defender_id": "u_def",
            "defender_hex": {"i": h_def.i, "j": h_def.j, "k": h_def.k},
        },
        "retreat_obligations": {"u_def": 1},
    }
    st = GameState(
        board=board,
        turn=TurnState("union", "Combat", 2, 1, 1, 0),
        session_state=session,
        session_state_key="hexdemo",
    )
    flow = build_retreat_fulfillment_flow(
        unit_id="u_def",
        path=(h_def, h_ret),
        moving_faction="confederate",
        budget_remaining=1.0,
        step_index=1,
    )
    st = st.with_engine_state({HEXENGINE_MOVEMENT_ARC_KEY: flow})
    st = with_arc_cursor(
        st, ArcCursor(arc_id=MOVEMENT_ARC_ID, segment_id="continue")
    )

    host = _Host(st)
    for action in combat_actions.apply_retreat_fulfillment_step(
        host.action_manager.current_state,
        "hexdemo",
        "confederate",
        {
            "unit_id": "u_def",
            "from_hex": {"i": h_def.i, "j": h_def.j, "k": h_def.k},
            "to_hex": {"i": h_ret.i, "j": h_ret.j, "k": h_ret.k},
        },
    ):
        host.action_manager.execute(action)

    resume_combat_arc_after_retreat_fulfillment(host)

    final = host.action_manager.current_state
    hx = engine_read_session_state(final, "hexdemo")
    assert isinstance(hx.get("advance"), dict)
    assert hx.get("advance", {}).get("faction") == "union"
    assert not hx.get("retreat_obligations")
    assert HEXENGINE_MOVEMENT_ARC_KEY not in final.engine_state

    cur = read_arc_cursor(final)
    assert cur is not None
    assert cur.arc_id == "combat"
    assert cur.segment_id == SEG_ADVANCE_GATE


def test_resume_combat_arc_from_resolve_segment_idempotent() -> None:
    """``resume_combat_arc_after_retreat_fulfillment`` tolerates stale movement payload."""
    h_att = Hex(0, 0, 0)
    h_def = Hex(1, -1, 0)
    h_ret = next(h for h in neighbors(h_def) if h != h_att)

    st = GameState.create_empty().with_board(
        BoardState(
            units={
                "u_att": UnitState(
                    unit_id="u_att",
                    unit_type="inf",
                    faction="union",
                    position=h_att,
                    active=True,
                ),
                "u_def": UnitState(
                    unit_id="u_def",
                    unit_type="inf",
                    faction="confederate",
                    position=h_ret,
                    active=True,
                ),
            }
        )
    )
    st = st.with_session_state(
        {
            "last_combat": {
                "outcome": "defender_retreat",
                "attacker_id": "u_att",
                "attacker_ids": ["u_att"],
                "defender_id": "u_def",
                "defender_hex": {"i": h_def.i, "j": h_def.j, "k": h_def.k},
            },
        },
        session_state_key="hexdemo",
    )
    host = _Host(st)
    host.action_manager.execute(
        SetArcCursor(ArcCursor(arc_id="combat", segment_id=SEG_RESOLVE))
    )

    resume_combat_arc_after_retreat_fulfillment(host)

    final = host.action_manager.current_state
    assert isinstance(
        engine_read_session_state(final, "hexdemo").get("advance"), dict
    )
    cur = read_arc_cursor(final)
    assert cur is not None
    assert cur.segment_id == SEG_ADVANCE_GATE
