"""
Phase 3b–3c: routing movement RPCs through the generic arc runner.

Covers stepwise continue (MoveUnit) and interrupt pass (PassMovementInterrupt) against
the engine movement arc. The runner is authoritative; rejections surface as errors.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace

from hexengine.arcs import ArcCursor, ArcSpec, SuspendedFrame, read_arc_cursor
from hexengine.arcs.movement_arc_decl import (
    MOVEMENT_ARC_ID,
    SEG_CONTINUE,
    SEG_INTERRUPT,
)
from hexengine.gamedef.builtin import InterleavedTwoFactionGameDefinition
from hexengine.hexes.types import Hex
from hexengine.hooks.arcs import ArcsHooks
from hexengine.hooks.core import ENGINE_MOVEMENT_ARC_PRESET
from hexengine.hooks.modification import MoveContext, ModificationHooks, MovementStepContext
from hexengine.hooks.title import TitleHooks
from hexengine.hooks.title import TitleHooks
from hexengine.server import GameServer
from hexengine.server.arcs import (
    drive_movement_arc_event,
    sync_movement_cursor_from_payload,
)
from hexengine.server.protocol import ActionRequest, JoinGameRequest
from hexengine.state import ActionManager, GameState
from hexengine.state.game_state import BoardState, LocationState, TurnState, UnitState
from hexengine.state.movement_arc import (
    HEXENGINE_MOVEMENT_ARC_KEY,
    MOVEMENT_ARC_GATE_AWAITING_CONTINUE,
    MOVEMENT_ARC_GATE_AWAITING_INTERRUPT,
    MOVEMENT_INTERRUPT_PHASE,
)


def _loc(h: Hex) -> LocationState:
    return LocationState(position=h, terrain_type="t", movement_cost=1.0)


def _always_stepwise(_ctx: MoveContext) -> bool:
    return True


def _blue_after_first_step(_ctx: MovementStepContext) -> tuple[str, ...]:
    return ("Blue",)


class StepwiseInterleaved(InterleavedTwoFactionGameDefinition):
    def __init__(self, modification: ModificationHooks) -> None:
        super().__init__()
        self._modification_hooks = modification

    @property
    def hooks(self) -> TitleHooks:
        b = super().hooks
        return TitleHooks(
            modification=self._modification_hooks,
            interaction=b.interaction,
            ui=b.ui,
            arcs=ArcsHooks(movement_arc=lambda: ENGINE_MOVEMENT_ARC_PRESET),
        )


class _Host:
    """Minimal stand-in with real movement arc spec (GameServer builds effects)."""

    def __init__(self, state: GameState, hooks: TitleHooks) -> None:
        self.hooks = hooks
        self.action_manager = ActionManager(state)
        self.sent: list[tuple[str, object]] = []
        self.broadcasts = 0
        self._movement_arc_spec_cache = None
        from hexengine.arcs import ArcSpec
        from hexengine.arcs.movement_arc_decl import resolve_moving_faction
        from hexengine.arcs.movement_arc_build import build_movement_arc
        from hexengine.server.arcs.movement_arc_effects import MovementArcEffects

        class _MovementHostAdapter:
            action_manager = self.action_manager
            hooks = self.hooks

            def _max_active_units_per_hex(self, state, unit_id):
                return None

            def _zoc_hexes_for_unit(self, state, unit_id):
                return None

            def _movement_step_cost_fn(self, unit_id):
                return None

            def _movement_step_total_cost(self, state, unit_id, from_h, to_h):
                return 1.0

        effects = MovementArcEffects(_MovementHostAdapter())  # type: ignore[arg-type]
        self._movement_arc_spec_cache = ArcSpec(
            arc=build_movement_arc(effects),
            owner_resolver=resolve_moving_faction,
        )

    def movement_arc_spec(self):
        return self._movement_arc_spec_cache

    async def _send_message(self, player_id: str, message: object) -> None:
        self.sent.append((player_id, message))

    async def _broadcast_state_update(self) -> None:
        self.broadcasts += 1


def _flow_payload(
    *,
    gate: str,
    step_index: int = 1,
    interrupt_queue: list[str] | None = None,
) -> dict:
    return {
        "schema": 1,
        "unit_id": "ru",
        "path": [
            {"i": 0, "j": 0, "k": 0},
            {"i": 1, "j": -1, "k": 0},
            {"i": 2, "j": -2, "k": 0},
        ],
        "step_index": step_index,
        "moving_faction": "Red",
        "budget_remaining": 2.0,
        "gate": gate,
        "interrupt_queue": interrupt_queue or [],
        "saved_turn": None,
    }


def test_sync_cursor_maps_continue_gate() -> None:
    st = GameState.create_empty().with_engine_state(
        {
            HEXENGINE_MOVEMENT_ARC_KEY: _flow_payload(
                gate=MOVEMENT_ARC_GATE_AWAITING_CONTINUE
            )
        }
    )
    host = _Host(st, StepwiseInterleaved(ModificationHooks()).hooks)
    sync_movement_cursor_from_payload(host)
    cur = read_arc_cursor(host.action_manager.current_state)
    assert cur == ArcCursor(arc_id=MOVEMENT_ARC_ID, segment_id=SEG_CONTINUE)


def test_sync_cursor_maps_interrupt_gate_with_suspend_frame() -> None:
    st = GameState.create_empty().with_engine_state(
        {
            HEXENGINE_MOVEMENT_ARC_KEY: _flow_payload(
                gate=MOVEMENT_ARC_GATE_AWAITING_INTERRUPT,
                interrupt_queue=["Blue"],
            )
        }
    )
    host = _Host(st, StepwiseInterleaved(ModificationHooks()).hooks)
    sync_movement_cursor_from_payload(host)
    cur = read_arc_cursor(host.action_manager.current_state)
    assert cur == ArcCursor(
        arc_id=MOVEMENT_ARC_ID,
        segment_id=SEG_INTERRUPT,
        suspended=SuspendedFrame(resume_segment_id=SEG_CONTINUE),
    )


def test_server_stepwise_move_routes_through_runner() -> None:
    mh = ModificationHooks(
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
        cur = read_arc_cursor(s2)
        assert cur is not None
        assert cur.arc_id == MOVEMENT_ARC_ID
        assert cur.segment_id == SEG_INTERRUPT
        assert cur.is_suspended

        pass_req = ActionRequest(
            action_type="PassMovementInterrupt",
            player_id="b1",
            params={},
        )
        await server.handle_message("b1", pass_req.to_message())
        s3 = server.game_state
        assert s3 is not None
        assert s3.turn.current_faction == "Red"
        cur3 = read_arc_cursor(s3)
        assert cur3 is not None
        assert cur3.segment_id == SEG_CONTINUE
        assert not cur3.is_suspended

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
        assert read_arc_cursor(s4) is None
        assert HEXENGINE_MOVEMENT_ARC_KEY not in s4.engine_state
        assert s4.board.units["ru"].position == c
        assert s4.turn.phase_actions_remaining == 1

    asyncio.run(run())


def test_drive_rejects_wrong_interrupt_owner() -> None:
    st = (
        GameState.create_empty()
        .with_engine_state(
            {
                HEXENGINE_MOVEMENT_ARC_KEY: _flow_payload(
                    gate=MOVEMENT_ARC_GATE_AWAITING_INTERRUPT,
                    interrupt_queue=["Blue"],
                )
            }
        )
        .with_turn(
            replace(
                GameState.create_empty().turn,
                current_faction="Blue",
                current_phase=MOVEMENT_INTERRUPT_PHASE,
            )
        )
    )
    host = _Host(st, StepwiseInterleaved(ModificationHooks()).hooks)
    sync_movement_cursor_from_payload(host)

    async def run() -> bool:
        return await drive_movement_arc_event(
            host,
            "x1",
            SimpleNamespace(faction="Red"),
            "PassMovementInterrupt",
            {},
        )

    assert asyncio.run(run()) is False


def test_movement_arc_spec_for_host_omits_when_hook_unbound() -> None:
    from hexengine.arcs.title.lookup import movement_arc_spec_for_host
    from hexengine.hooks.title import TitleHooks

    class Host:
        hooks = TitleHooks()
        movement_calls = 0

        def movement_arc_spec(self):
            self.movement_calls += 1
            return None

    host = Host()
    assert movement_arc_spec_for_host(host) is None
    assert host.movement_calls == 0


def test_movement_arc_spec_for_host_uses_preset_via_host() -> None:
    from hexengine.arcs.title.lookup import movement_arc_spec_for_host
    from hexengine.hooks.arcs import ArcsHooks
    from hexengine.hooks.title import TitleHooks

    sentinel = object()

    class Host:
        hooks = TitleHooks(
            arcs=ArcsHooks(movement_arc=lambda: ENGINE_MOVEMENT_ARC_PRESET)
        )

        def movement_arc_spec(self):
            return sentinel

    assert movement_arc_spec_for_host(Host()) is sentinel


def test_drive_movement_arc_retreat_open_writes_payload() -> None:
    import asyncio
    from types import SimpleNamespace

    from hexengine.hexes.math import neighbors
    from hexengine.hooks.modification import ModificationHooks
    from hexengine.server.arcs import (
        MovementArcDriveOutcome,
        drive_movement_arc_retreat_open,
    )
    from hexengine.state.game_state import BoardState, TurnState, UnitState
    from hexengine.state.engine_session_state import engine_bucket

    h0 = Hex(0, 0, 0)
    h1 = next(iter(neighbors(h0)))
    h2 = next(n for n in neighbors(h1) if n != h0)
    board = BoardState(
        units={
            "u": UnitState(
                unit_id="u",
                unit_type="inf",
                faction="Red",
                position=h0,
                active=True,
            ),
        }
    )
    st = GameState(
        board=board,
        turn=TurnState("Red", "Move", 2, 1, 0, 0),
        session_state={"retreat_obligations": {"u": 2}},
        session_state_key="pack",
    )

    class Host:
        def __init__(self) -> None:
            self.hooks = StepwiseInterleaved(
                ModificationHooks(
                    retreat_obligation_hexes_remaining=lambda _s, uid: 2
                    if uid == "u"
                    else None,
                )
            ).hooks
            self.action_manager = ActionManager(st)
            self.messages: list = []

        def movement_arc_spec(self):
            from hexengine.server.arcs.movement_arc_spec import (
                build_host_bound_movement_arc_spec,
            )

            return build_host_bound_movement_arc_spec(self)

        async def _send_message(self, _pid: str, message: object) -> None:
            self.messages.append(message)

        async def _send_error(self, _pid: str, message: str) -> None:
            self.messages.append(message)

        async def _broadcast_state_update(self) -> None:
            return None

    host = Host()
    params = {
        "unit_id": "u",
        "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
        "to_hex": {"i": h1.i, "j": h1.j, "k": h1.k},
        "path": [
            {"i": h0.i, "j": h0.j, "k": h0.k},
            {"i": h1.i, "j": h1.j, "k": h1.k},
            {"i": h2.i, "j": h2.j, "k": h2.k},
        ],
    }
    assert (
        asyncio.run(
            drive_movement_arc_retreat_open(
                host,
                "p1",
                SimpleNamespace(faction="Red"),
                params,
            )
        )
        == MovementArcDriveOutcome.ACCEPTED
    )
    final = host.action_manager.current_state
    assert final.board.units["u"].position == h1
    arc = engine_bucket(final, HEXENGINE_MOVEMENT_ARC_KEY)
    assert isinstance(arc, dict)
    assert arc.get("retreat_fulfillment") is True
    assert arc.get("step_index") == 1
    assert read_arc_cursor(final) == ArcCursor(
        arc_id=MOVEMENT_ARC_ID, segment_id=SEG_CONTINUE
    )


def test_drive_movement_arc_retreat_open_single_hex_completes_via_binding() -> None:
    import asyncio
    from types import SimpleNamespace

    from hexengine.hexes.math import neighbors
    from hexengine.hooks.arcs import ArcsHooks
    from hexengine.hooks.modification import ModificationHooks
    from hexengine.server.arcs import (
        drive_movement_arc_retreat_open,
        handle_authority_retreat_path_move_unit,
    )
    from hexengine.server.protocol import ActionRequest
    from hexengine.state.game_state import BoardState, TurnState, UnitState
    from hexengine.state.engine_session_state import engine_read_session_state

    h0 = Hex(0, 0, 0)
    h1 = next(iter(neighbors(h0)))

    class StubBinding:
        def apply_retreat_step(self, ctx):
            from hexengine.hooks.bucket import ApplyBucketPatch, BucketPatch

            return [
                ApplyBucketPatch(
                    "pack",
                    BucketPatch(values={"retreat_obligations": {}}),
                )
            ]

    class Host:
        def __init__(self) -> None:
            self.hooks = TitleHooks(
                modification=ModificationHooks(
                    retreat_obligation_hexes_remaining=lambda _s, uid: 1
                    if uid == "u"
                    else None,
                    retreat_blocked_hexes=lambda _s, _uid: None,
                ),
                arcs=ArcsHooks(
                    movement_arc=lambda: ENGINE_MOVEMENT_ARC_PRESET,
                    combat_rules_binding=lambda: StubBinding(),
                ),
            )
            board = BoardState(
                units={
                    "u": UnitState(
                        unit_id="u",
                        unit_type="inf",
                        faction="Red",
                        position=h0,
                        active=True,
                    ),
                }
            )
            self.action_manager = ActionManager(
                GameState(
                    board=board,
                    turn=TurnState("Red", "Move", 2, 1, 0, 0),
                    session_state={"retreat_obligations": {"u": 1}},
                    session_state_key="pack",
                )
            )
            self.logger = __import__("logging").getLogger("test")

        def movement_arc_spec(self):
            from hexengine.server.arcs.movement_arc_spec import (
                build_host_bound_movement_arc_spec,
            )

            return build_host_bound_movement_arc_spec(self)

        async def _send_message(self, _pid: str, message: object) -> None:
            pass

        async def _send_error(self, _pid: str, message: str) -> None:
            raise AssertionError(message)

        async def _broadcast_state_update(self) -> None:
            pass

        def _validate_move_unit_request(self, *_a, **_k) -> None:
            return None

        def _max_active_units_per_hex(self, *_a, **_k):
            return None

        def _zoc_hexes_for_unit(self, *_a, **_k):
            return None

        def _movement_step_cost_fn(self, *_a):
            return None

        def _retreat_obligation_hexes_remaining(self, _st, uid):
            return 1 if uid == "u" else None

        def _movement_budget_for_unit(self, *_a):
            return 4.0

        def _movement_step_total_cost(self, *_a, **_k):
            return 1.0

        async def _send_move_unit_success_and_broadcast(self, _pid: str) -> None:
            pass

    host = Host()
    req = ActionRequest(
        action_type="MoveUnit",
        player_id="p1",
        params={
            "unit_id": "u",
            "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
            "to_hex": {"i": h1.i, "j": h1.j, "k": h1.k},
            "path": [
                {"i": h0.i, "j": h0.j, "k": h0.k},
                {"i": h1.i, "j": h1.j, "k": h1.k},
            ],
        },
    )

    async def run() -> None:
        handled = await handle_authority_retreat_path_move_unit(
            host,
            "p1",
            SimpleNamespace(faction="Red"),
            req,
            host.action_manager.current_state,
            retreat_remaining=1,
            uid_for_move="u",
        )
        assert handled is True

    asyncio.run(run())
    final = host.action_manager.current_state
    assert final.board.units["u"].position == h1
    assert not engine_read_session_state(final, "pack").get("retreat_obligations")
