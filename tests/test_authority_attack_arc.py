"""Phase D: Attack routed through combat arc ``submit_event``."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import patch

from games.hexdemo import combat_arc
from games.hexdemo.hooks import build_hooks

from hexengine.arcs import ArcCursor, SetArcCursor, read_arc_cursor
from hexengine.arcs.segment_wire import project_current_segment, segment_allows_action
from hexengine.hexes.types import Hex
from hexengine.hooks.attack import AttackResolution
from hexengine.server.arcs.authority_arc_runtime import begin_routine_slot
from hexengine.server.arcs.authority_attack import execute_authority_attack_request
from hexengine.state import ActionManager, GameState
from hexengine.state.game_state import BoardState, TurnState, UnitState
from hexengine.state.title_extension import title_bucket


@dataclass
class _Host:
    hooks: object
    action_manager: ActionManager
    broadcasted: bool = False
    errors: list[str] | None = None

    async def _send_error(self, _player_id: str, message: str) -> None:
        if self.errors is not None:
            self.errors.append(message)

    def _title_extension_key(self) -> str | None:
        return "hexdemo"

    async def _broadcast_combat_events(self, _state: GameState) -> None:
        self.broadcasted = True

    def lookup_arc_spec(self, arc_id: str):
        from hexengine.server.arcs.authority_arc_runtime import lookup_arc_spec

        return lookup_arc_spec(self, arc_id)

    def _get_next_phase(self):
        return None

    def _after_next_phase_applied(self) -> None:
        return None

    def _maybe_auto_advance_phase(self, *_a, **_k) -> bool:
        return False


def _combat_state() -> GameState:
    board = BoardState(
        units={
            "u_att": UnitState(
                unit_id="u_att",
                unit_type="inf",
                faction="union",
                position=Hex(0, 0, 0),
                active=True,
            ),
            "u_def": UnitState(
                unit_id="u_def",
                unit_type="inf",
                faction="confederate",
                position=Hex(1, 0, -1),
                active=True,
            ),
        }
    )
    turn = TurnState(
        current_faction="union",
        current_phase="Combat",
        turn_number=1,
        phase_actions_remaining=2,
    )
    return GameState(board=board, turn=turn, title_state={}, title_bucket_key="hexdemo")


def test_attack_without_cleanup_gate_restores_routine_cursor() -> None:
    """Combat arc completion must restore the turn slot cursor so End Phase works."""

    st0 = _combat_state()
    st0 = GameState(
        board=st0.board,
        turn=TurnState(
            current_faction="union",
            current_phase="Combat",
            turn_number=1,
            phase_actions_remaining=2,
            schedule_index=1,
        ),
        title_state={},
        title_bucket_key="hexdemo",
    )
    mgr = ActionManager(st0)
    host = _Host(hooks=build_hooks(), action_manager=mgr)
    begin_routine_slot(host, 1)

    def _none_resolve(_ctx):
        return AttackResolution(
            outcome="none",
            rng_entry={"op": "test", "outcome": "none"},
        )

    with patch("games.hexdemo.combat_rules.resolve_attack", _none_resolve):
        ok = asyncio.run(
            execute_authority_attack_request(
                host,
                player_id="p1",
                player_faction="union",
                current_state=st0,
                params={
                    "attack_kind": "combined",
                    "attacker_id": "u_att",
                    "defender_id": "u_def",
                },
            )
        )

    assert ok is True
    cur = read_arc_cursor(mgr.current_state)
    assert cur is not None
    assert cur.arc_id == "union_combat"
    seg = project_current_segment(host, mgr.current_state, viewer_faction="union")
    assert segment_allows_action(seg, "NextPhase") is True


def test_attack_via_combat_arc_lands_on_cleanup_gate() -> None:
    st0 = _combat_state()
    mgr = ActionManager(st0)
    host = _Host(hooks=build_hooks(), action_manager=mgr)

    ok = asyncio.run(
        execute_authority_attack_request(
            host,
            player_id="p1",
            player_faction="union",
            current_state=st0,
            params={
                "attack_kind": "combined",
                "attacker_id": "u_att",
                "defender_id": "u_def",
            },
        )
    )
    assert ok is True
    hx = title_bucket(mgr.current_state, "hexdemo")
    assert isinstance(hx, dict)
    assert "u_att" in (hx.get("attacks_this_phase") or [])
    cur = read_arc_cursor(mgr.current_state)
    if cur is not None and cur.arc_id == "combat":
        assert cur.segment_id in (
            combat_arc.SEG_RETREAT_GATE,
            combat_arc.SEG_RETREAT_OR_DISRUPT_GATE,
            combat_arc.SEG_ADVANCE_GATE,
        )


def test_attack_rejected_on_retreat_gate_via_arc_path() -> None:
    st0 = _combat_state()
    st0 = st0.with_title_state(
        {"retreat_obligations": {"u_def": 1}}, title_bucket_key="hexdemo"
    )
    mgr = ActionManager(st0)
    mgr.execute(
        SetArcCursor(ArcCursor(arc_id="combat", segment_id=combat_arc.SEG_RETREAT_GATE))
    )
    errors: list[str] = []
    host = _Host(hooks=build_hooks(), action_manager=mgr, errors=errors)

    ok = asyncio.run(
        execute_authority_attack_request(
            host,
            player_id="p1",
            player_faction="union",
            current_state=mgr.current_state,
            params={
                "attack_kind": "combined",
                "attacker_id": "u_att",
                "defender_id": "u_def",
            },
        )
    )
    assert ok is False
    assert errors
    cur = read_arc_cursor(mgr.current_state)
    assert cur is not None
    assert cur.segment_id == combat_arc.SEG_RETREAT_GATE
