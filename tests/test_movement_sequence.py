"""Stepwise movement: pathfinding, extension actions, and server authority."""

from __future__ import annotations

import asyncio

from hexengine.gamedef.builtin import InterleavedTwoFactionGameDefinition
from hexengine.hexes.types import Hex
from hexengine.hooks.arcs import ArcsHooks
from hexengine.hooks.core import ENGINE_MOVEMENT_ARC_PRESET
from hexengine.hooks.movement import MoveContext, MovementHooks, MovementStepContext
from hexengine.hooks.title import TitleHooks
from hexengine.server import ActionRequest, GameServer
from hexengine.server.protocol import JoinGameRequest
from hexengine.state.action_manager import ActionManager
from hexengine.state.actions import ResolvePassMovementInterrupt
from hexengine.state.game_state import (
    BoardState,
    GameState,
    LocationState,
    TurnState,
    UnitState,
)
from hexengine.state.logic import is_valid_move, shortest_move_path
from hexengine.state.movement_arc import (
    HEXENGINE_MOVEMENT_ARC_KEY,
    MOVEMENT_ARC_GATE_AWAITING_CONTINUE,
    MOVEMENT_INTERRUPT_PHASE,
)
from hexengine.state.engine_session_state import engine_bucket


def _loc(h: Hex) -> LocationState:
    return LocationState(position=h, terrain_type="t", movement_cost=1.0)


def test_shortest_move_path_straight_line() -> None:
    a = Hex(0, 0, 0)
    b = Hex(1, -1, 0)
    c = Hex(2, -2, 0)
    board = BoardState(
        locations={a: _loc(a), b: _loc(b), c: _loc(c)},
        units={"u": UnitState("u", "x", "Red", a, active=True)},
    )
    st = GameState(
        board=board,
        turn=TurnState("Red", "Movement", 2, 1, 0, 0),
    )
    path = shortest_move_path(st, "u", c, 4.0, zoc_hexes=None, step_cost=None)
    assert path == (a, b, c)


def test_resolve_pass_movement_interrupt_restores_turn() -> None:
    saved = TurnState(
        current_faction="Red",
        current_phase="Movement",
        phase_actions_remaining=2,
        turn_number=3,
        schedule_index=1,
        global_tick=5,
    )
    arc_payload = {
        "schema": 1,
        "unit_id": "u1",
        "path": [
            {"i": 0, "j": 0, "k": 0},
            {"i": 1, "j": -1, "k": 0},
        ],
        "step_index": 1,
        "moving_faction": "Red",
        "budget_remaining": 1.0,
        "gate": "awaiting_interrupt",
        "interrupt_queue": ["Blue"],
        "saved_turn": {
            "current_faction": saved.current_faction,
            "current_phase": saved.current_phase,
            "phase_actions_remaining": saved.phase_actions_remaining,
            "turn_number": saved.turn_number,
            "schedule_index": saved.schedule_index,
            "global_tick": saved.global_tick,
        },
    }
    board = BoardState(
        units={
            "u1": UnitState("u1", "x", "Red", Hex(1, -1, 0), active=True),
        }
    )
    st0 = GameState(
        board=board,
        turn=TurnState(
            current_faction="Blue",
            current_phase=MOVEMENT_INTERRUPT_PHASE,
            phase_actions_remaining=1,
            turn_number=3,
            schedule_index=1,
            global_tick=5,
        ),
        engine_state={HEXENGINE_MOVEMENT_ARC_KEY: arc_payload},
    )
    mgr = ActionManager(st0)
    mgr.execute(ResolvePassMovementInterrupt("Blue"))
    st1 = mgr.current_state
    assert st1.turn.current_faction == "Red"
    assert st1.turn.current_phase == "Movement"
    assert (
        st1.engine_state[HEXENGINE_MOVEMENT_ARC_KEY]["gate"]
        == MOVEMENT_ARC_GATE_AWAITING_CONTINUE
    )


def _always_stepwise(_ctx: MoveContext) -> bool:
    return True


def _blue_after_first_step(_ctx: MovementStepContext) -> tuple[str, ...]:
    return ("Blue",)


class StepwiseInterleaved(InterleavedTwoFactionGameDefinition):
    """`InterleavedTwoFactionGameDefinition` with custom movement hooks."""

    def __init__(self, movement: MovementHooks) -> None:
        super().__init__()
        self._movement_hooks = movement

    @property
    def hooks(self) -> TitleHooks:
        b = super().hooks
        return TitleHooks(
            movement=self._movement_hooks,
            attack=b.attack,
            ui=b.ui,
            arcs=ArcsHooks(movement_arc=lambda: ENGINE_MOVEMENT_ARC_PRESET),
        )


def test_server_stepwise_move_opens_interrupt_queue() -> None:
    mh = MovementHooks(
        resolve_move_as_steps=_always_stepwise,
        movement_interrupt_factions_after_step=_blue_after_first_step,
    )
    gd = StepwiseInterleaved(mh)

    a = Hex(0, 0, 0)
    b = Hex(1, -1, 0)
    c = Hex(2, -2, 0)
    board = BoardState(
        locations={a: _loc(a), b: _loc(b), c: _loc(c)},
        units={
            "ru": UnitState("ru", "x", "Red", a, active=True),
            "bu": UnitState("bu", "x", "Blue", Hex(5, -2, -3), active=True),
        },
    )
    st = GameState(board=board, turn=TurnState("Red", "Movement", 2, 1, 0, 0))
    assert is_valid_move(st, "ru", c, 4.0)

    server = GameServer(st, game_definition=gd)

    async def run() -> None:
        await server.handle_message(
            "r1", JoinGameRequest(player_name="R", faction="Red").to_message()
        )
        await server.handle_message(
            "b1", JoinGameRequest(player_name="B", faction="Blue").to_message()
        )
        req = ActionRequest(
            action_type="MoveUnit",
            player_id="r1",
            params={
                "unit_id": "ru",
                "from_hex": {"i": a.i, "j": a.j, "k": a.k},
                "to_hex": {"i": c.i, "j": c.j, "k": c.k},
            },
        )
        await server.handle_message("r1", req.to_message())
        s2 = server.game_state
        assert s2 is not None
        arc = engine_bucket(s2, HEXENGINE_MOVEMENT_ARC_KEY)
        assert isinstance(arc, dict)
        assert arc.get("gate") == "awaiting_interrupt"
        assert s2.turn.current_faction == "Blue"
        assert s2.board.units["ru"].position == b

        pass_req = ActionRequest(
            action_type="PassMovementInterrupt",
            player_id="b1",
            params={},
        )
        await server.handle_message("b1", pass_req.to_message())
        s3 = server.game_state
        assert s3 is not None
        assert s3.turn.current_faction == "Red"
        arc3 = engine_bucket(s3, HEXENGINE_MOVEMENT_ARC_KEY)
        assert isinstance(arc3, dict)
        assert arc3.get("gate") == MOVEMENT_ARC_GATE_AWAITING_CONTINUE

        cont = ActionRequest(
            action_type="MoveUnit",
            player_id="r1",
            params={
                "unit_id": "ru",
                "from_hex": {"i": b.i, "j": b.j, "k": b.k},
                "to_hex": {"i": c.i, "j": c.j, "k": c.k},
            },
        )
        await server.handle_message("r1", cont.to_message())
        s4 = server.game_state
        assert s4 is not None
        assert HEXENGINE_MOVEMENT_ARC_KEY not in s4.engine_state
        assert s4.board.units["ru"].position == c
        assert s4.turn.phase_actions_remaining == 1

    asyncio.run(run())
