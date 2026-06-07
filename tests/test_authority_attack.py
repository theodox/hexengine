"""Tests for `hexengine.server.arcs.authority_attack` pipeline metadata and helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from hexengine.arcs import ArcCursor, ArcSpec, SetArcCursor
from hexengine.authoring.patterns.combat import (
    CombatArcGateKinds,
    build_combat_cleanup_arc,
)
from hexengine.hexes.types import Hex
from hexengine.hooks.arcs import ArcsHooks
from hexengine.hooks.attack import (
    AfterAttackAppliedContext,
    AttackContext,
    AttackHooks,
    AttackResolution,
)
from hexengine.hooks.title import TitleHooks
from hexengine.server.arcs.authority_attack import (
    ATTACK_BLOCKED_BY_ACTIVE_SEGMENT_MSG,
    AUTHORITY_ATTACK_PIPELINE,
    AuthorityAttackPipelineStep,
    dedupe_wire_id_list,
    execute_authority_attack_request,
    normalize_attack_party_ids,
)
from hexengine.state import GameState
from hexengine.state.action_manager import ActionManager
from hexengine.state.game_state import BoardState, TurnState, UnitState
from hexengine.state.title_extension import title_bucket

EXPECTED_ORDER = (
    AuthorityAttackPipelineStep.NORMALIZE_WIRE_AND_PARTIES,
    AuthorityAttackPipelineStep.SUBMIT_ATTACK_EVENT,
    AuthorityAttackPipelineStep.BROADCAST_COMBAT_EVENTS,
    AuthorityAttackPipelineStep.MAYBE_AUTO_ADVANCE_PHASE,
)


def test_authority_attack_pipeline_order_is_stable() -> None:
    assert AUTHORITY_ATTACK_PIPELINE == EXPECTED_ORDER
    assert len(AUTHORITY_ATTACK_PIPELINE) == 4


def test_normalize_attack_party_ids_anchor_first() -> None:
    p = {"attacker_ids": ["b", "a"]}
    assert normalize_attack_party_ids(p, anchor_id="a", plural_key="attacker_ids") == (
        "a",
        "b",
    )


def test_dedupe_wire_id_list() -> None:
    assert dedupe_wire_id_list(["x", " x ", "y", "x"]) == ["x", "y"]


@dataclass
class _AttackHost:
    hooks: TitleHooks
    action_manager: ActionManager
    broadcasted: bool = False
    auto_advance_called: bool = False
    errors: list[str] | None = None

    async def _send_error(self, player_id: str, message: str) -> None:
        if self.errors is not None:
            self.errors.append(message)
            return
        raise AssertionError(f"{player_id}: {message}")

    def _title_extension_key(self) -> str | None:
        return "testpack"

    def lookup_arc_spec(self, arc_id: str):
        from hexengine.server.arcs.authority_arc_runtime import lookup_arc_spec

        return lookup_arc_spec(self, arc_id)

    async def _broadcast_combat_events(self, state: GameState) -> None:
        self.broadcasted = True

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
        self.auto_advance_called = True
        return False


class _AuthorityAttackTestEffects:
    hooks: TitleHooks | None = None

    def attack_arc_effect(self, ctx):
        from hexengine.server.arcs.authority_attack_commit import (
            build_attack_context_from_wire,
            collect_authority_attack_actions,
            resolve_authority_attack,
        )

        if self.hooks is None:
            raise RuntimeError("authority attack test hooks not wired")
        commit_host = SimpleNamespace(hooks=self.hooks)
        player_faction = str(ctx.owner_faction or "").strip()
        attack_ctx = build_attack_context_from_wire(
            ctx.state, player_faction, dict(ctx.params)
        )
        resolution, outcome_from_resolve = resolve_authority_attack(
            commit_host, attack_ctx
        )
        extension_key = str(
            ctx.extension_key or ctx.state.title_bucket_key or ""
        ).strip()
        return collect_authority_attack_actions(
            commit_host,
            attack_context=attack_ctx,
            resolution=resolution,
            extension_key=extension_key,
            outcome_from_resolve=outcome_from_resolve,
        )

    def has_pending_retreat(self, _ctx) -> bool:
        return False

    def disrupt_offered(self, _ctx) -> bool:
        return False

    def advance_available(self, _ctx) -> bool:
        return False

    def is_retreat_fulfillment(self, _ctx) -> bool:
        return False

    def is_combat_advance_move(self, _ctx) -> bool:
        return False

    def apply_retreat_step(self, _ctx) -> list:
        return []

    def disrupt_instead(self, _ctx) -> list:
        return []

    def open_advance(self, _ctx) -> list:
        return []

    def resolve_advance(self, _ctx) -> list:
        return []

    def clear_advance_gate(self, _ctx) -> list:
        return []


_AUTHORITY_ATTACK_TEST_EFFECTS = _AuthorityAttackTestEffects()
_AUTHORITY_ATTACK_TEST_ARC = ArcSpec(
    arc=build_combat_cleanup_arc(
        _AUTHORITY_ATTACK_TEST_EFFECTS,
        CombatArcGateKinds(
            awaiting_retreat="awaiting_retreat",
            awaiting_retreat_or_disrupt="awaiting_retreat_or_disrupt",
            awaiting_advance="awaiting_advance",
        ),
        attack_effect=_AUTHORITY_ATTACK_TEST_EFFECTS.attack_arc_effect,
    ),
)


def _attack_test_hooks(attack: AttackHooks) -> TitleHooks:
    _AUTHORITY_ATTACK_TEST_EFFECTS.hooks = TitleHooks(attack=attack)
    return TitleHooks(
        arcs=ArcsHooks(combat_arc=lambda: _AUTHORITY_ATTACK_TEST_ARC),
        attack=attack,
    )


def _two_unit_combat_state() -> GameState:
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
    )
    return GameState(
        board=board, turn=turn, title_state={}, title_bucket_key="testpack"
    )


def test_combat_outcome_after_applied_follow_ups_run_before_broadcast() -> None:
    st0 = _two_unit_combat_state()
    mgr = ActionManager(st0)
    marker = {"patch_applied": False}

    def validate(_ctx: AttackContext) -> None:
        return None

    def resolve(_ctx: AttackContext) -> AttackResolution:
        return AttackResolution(outcome="none")

    def outcome_after_applied(ctx: AfterAttackAppliedContext):
        from hexengine.hooks.combat_outcome import CombatOutcome

        marker["patch_applied"] = True
        return CombatOutcome(
            bucket_patch={"after_attack_hook": True},
        )

    host = _AttackHost(
        hooks=_attack_test_hooks(
            AttackHooks(
                validate_attack=validate,
                resolve_attack=resolve,
                combat_outcome_after_applied=outcome_after_applied,
            )
        ),
        action_manager=mgr,
    )

    ok = asyncio.run(
        execute_authority_attack_request(
            host,
            player_id="p1",
            player_faction="union",
            current_state=st0,
            params={
                "attack_kind": "combined",
                "attacker_id": "a",
                "defender_id": "d",
            },
        )
    )
    assert ok is True
    assert marker["patch_applied"] is True
    assert host.broadcasted is True
    hx = title_bucket(mgr.current_state, "testpack")
    assert isinstance(hx, dict)
    assert hx.get("after_attack_hook") is True


def test_attack_rejected_on_retreat_gate_before_title_validate() -> None:
    """Engine segment gate runs before ``validate_attack`` for extension-key titles."""
    import dataclasses

    from games.hexdemo import combat_arc
    from games.hexdemo.hooks import build_hooks

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
        phase_actions_remaining=1,
        turn_number=1,
        schedule_index=0,
        global_tick=0,
    )
    st = GameState(
        board=board,
        turn=turn,
        title_state={"retreat_obligations": {"u_def": 1}},
        title_bucket_key="hexdemo",
        rng_log=(),
    )
    mgr = ActionManager(st)
    mgr.execute(
        SetArcCursor(ArcCursor(arc_id="combat", segment_id=combat_arc.SEG_RETREAT_GATE))
    )
    st_gate = mgr.current_state

    validate_called: list[int] = []
    base_hooks = build_hooks()

    def _tracking_validate(_ctx: AttackContext) -> None:
        validate_called.append(1)

    hooks = dataclasses.replace(
        base_hooks,
        attack=dataclasses.replace(
            base_hooks.attack,
            validate_attack=_tracking_validate,
            resolve_attack=lambda _ctx: AttackResolution(outcome="none"),
        ),
    )
    errors: list[str] = []
    host = _AttackHost(hooks=hooks, action_manager=mgr, errors=errors)

    ok = asyncio.run(
        execute_authority_attack_request(
            host,
            player_id="p1",
            player_faction="union",
            current_state=st_gate,
            params={
                "attack_kind": "combined",
                "attacker_id": "u_att",
                "defender_id": "u_def",
            },
        )
    )
    assert ok is False
    assert not validate_called
    assert errors == [ATTACK_BLOCKED_BY_ACTIVE_SEGMENT_MSG]
