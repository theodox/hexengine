"""Arc capability discovery from declared graphs (charter phase 2)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from hexengine.arcs import (
    CURRENT,
    ArcSpec,
    arc_commit_segment_for_action,
    arc_event_segments,
    arc_supports_action_type,
)
from hexengine.authoring import arc
from hexengine.authoring.patterns.combat import (
    CombatArcGateUiModes,
    build_combat_cleanup_arc,
)
from hexengine.hexes.types import Hex
from hexengine.hooks.arcs import ArcsHooks
from hexengine.hooks.interaction import InteractionHooks, AttackResolution
from hexengine.hooks.title import TitleHooks
from hexengine.server.arcs.authority_attack import execute_authority_attack_request
from hexengine.state import GameState
from hexengine.state.action_manager import ActionManager
from hexengine.state.game_state import BoardState, TurnState, UnitState


def test_arc_supports_action_type_from_event_transitions() -> None:
    combat = build_combat_cleanup_arc(
        SimpleNamespace(
            has_pending_retreat=lambda _c: False,
            disrupt_offered=lambda _c: False,
            advance_available=lambda _c: False,
            is_retreat_fulfillment=lambda _c: False,
            is_combat_advance_move=lambda _c: False,
            apply_retreat_step=lambda _c: [],
            disrupt_instead=lambda _c: [],
            open_advance=lambda _c: [],
            resolve_advance=lambda _c: [],
            clear_advance_gate=lambda _c: [],
        ),
        CombatArcGateUiModes(
            awaiting_retreat="awaiting_retreat",
            awaiting_retreat_or_disrupt="awaiting_retreat_or_disrupt",
            awaiting_advance="awaiting_advance",
        ),
        attack_effect=lambda _ctx: [],
    )
    assert arc_supports_action_type(combat, "Attack") is True
    assert arc_supports_action_type(combat, "CombatAdvance") is True
    assert arc_supports_action_type(combat, "NoSuchVerb") is False


def test_arc_event_segments_declaration_order() -> None:
    with arc("demo") as a:
        with a.segment("beta", owner=CURRENT) as s:
            s.on("Foo", goto="gamma")
        with a.segment("alpha", owner=CURRENT) as s:
            s.on("Foo", goto="beta")
        with a.segment("gamma", owner=CURRENT) as s:
            s.on("Bar", done=True)
    graph = a.build()
    assert arc_event_segments(graph, "Foo") == ("beta", "alpha")
    assert arc_commit_segment_for_action(graph, "Foo") == "beta"


def test_custom_strike_segment_id_supports_attack() -> None:
    with arc("fighting", entry="strike") as a:
        with a.segment("strike", owner=CURRENT, ui_mode="combat") as s:
            s.on("Attack", done=True)
    graph = a.build()
    assert arc_event_segments(graph, "Attack") == ("strike",)
    assert arc_commit_segment_for_action(graph, "Attack") == "strike"


@dataclass
class _StrikeHost:
    hooks: TitleHooks
    action_manager: ActionManager
    errors: list[str]

    async def _send_error(self, player_id: str, message: str) -> None:
        self.errors.append(message)

    def _engine_session_state_key(self) -> str | None:
        return "testpack"

    def lookup_arc_spec(self, arc_id: str):
        from hexengine.server.arcs.authority_arc_runtime import lookup_arc_spec

        return lookup_arc_spec(self, arc_id)

    async def _broadcast_combat_events(self, state: GameState) -> None:
        return None

    def _get_next_phase(self) -> dict[str, Any]:
        return {}

    def _after_next_phase_applied(self) -> None:
        return None

    def _maybe_auto_advance_phase(
        self,
        raw: bool | object,
        *,
        catalog_path: str | None,
        log_reason: str,
    ) -> bool:
        return False


def test_authority_attack_uses_strike_segment_not_engine_id() -> None:
    """Interaction commit segment is discovered from Event('Attack'), not id ``attack``."""

    def attack_effect(_ctx):
        return []

    with arc("fighting", entry="strike") as a:
        with a.segment("strike", owner=CURRENT) as s:
            s.on("Attack", done=True, effect=attack_effect)
    spec = ArcSpec(arc=a.build())

    board = BoardState(
        units={
            "a": UnitState(
                unit_id="a",
                unit_type="inf",
                faction="union",
                position=Hex(0, 0, 0),
                active=True,
            ),
            "d": UnitState(
                unit_id="d",
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
        phase_actions_remaining=1,
        schedule_index=0,
        global_tick=0,
    )
    st = GameState(
        board=board,
        turn=turn,
        session_state={},
        session_state_key="testpack",
    )
    mgr = ActionManager(st)
    hooks = TitleHooks(
        arcs=ArcsHooks(combat_arc=lambda: spec),
        interaction=InteractionHooks(
            validate_attack=lambda _ctx: None,
            resolve_attack=lambda _ctx: AttackResolution(outcome="none"),
        ),
    )
    host = _StrikeHost(hooks=hooks, action_manager=mgr, errors=[])

    ok = asyncio.run(
        execute_authority_attack_request(
            host,
            player_id="p1",
            player_faction="union",
            current_state=st,
            params={
                "attack_kind": "combined",
                "attacker_id": "a",
                "defender_id": "d",
            },
        )
    )
    assert ok is True, host.errors
    assert host.errors == []
