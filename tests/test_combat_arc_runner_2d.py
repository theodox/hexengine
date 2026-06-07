"""Phase 2d: obligation clear and advance moves without combat_gate mirror."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace

from games.hexdemo import combat_actions, combat_arc
from games.hexdemo.hooks import build_hooks

from hexengine.arcs import ArcCursor, SetArcCursor, read_arc_cursor
from hexengine.hexes.types import Hex
from hexengine.server.arcs import drive_combat_arc_event
from hexengine.state import ActionManager, GameState
from hexengine.state.actions import ClearUnitRetreatObligation
from hexengine.state.game_state import UnitState
from hexengine.state.title_extension import title_bucket


def test_clear_unit_retreat_obligation_does_not_touch_segment_state() -> None:
    st = GameState.create_empty().with_title_state(
        {"retreat_obligations": {"u1": 1}},
        title_bucket_key="hexdemo",
    )
    mgr = ActionManager(st)
    mgr.execute(ClearUnitRetreatObligation("u1", "hexdemo"))
    hx = title_bucket(mgr.current_state, "hexdemo")
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
    st = st.with_title_state(
        {"retreat_obligations": {"u1": 1}},
        title_bucket_key="hexdemo",
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
    hx = title_bucket(mgr.current_state, "hexdemo")
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
    st = st.with_title_state(
        {
            "advance": {
                "faction": "union",
                "attacker_id": "u_att",
                "unit_ids": ["u_att"],
                "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
                "to_hex": {"i": h1.i, "j": h1.j, "k": h1.k},
            },
        },
        title_bucket_key="hexdemo",
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
        drive_combat_arc_event(
            host, "p1", SimpleNamespace(faction="union"), "MoveUnit", params
        )
    )
    assert handled is True
    final = host.action_manager.current_state
    assert final.board.units["u_att"].position == h1
    cur = read_arc_cursor(final)
    assert cur is None or cur.arc_id != "combat"
    hx = title_bucket(final, "hexdemo")
    assert "advance" not in hx
