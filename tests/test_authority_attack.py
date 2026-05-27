"""Tests for `hexengine.server.arcs.authority_attack` pipeline metadata and helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from hexengine.hexes.types import Hex
from hexengine.hooks.attack import (
    AttackContext,
    AttackHooks,
    AttackResolution,
    AfterAttackAppliedContext,
)
from hexengine.hooks.core import ENGINE_DEFAULT
from hexengine.hooks.title import TitleHooks
from hexengine.server.arcs.authority_attack import (
    AUTHORITY_ATTACK_PIPELINE,
    AuthorityAttackPipelineStep,
    dedupe_wire_id_list,
    execute_authority_attack_request,
    normalize_attack_party_ids,
)
from hexengine.state import GameState
from hexengine.state.title_extension import title_bucket
from hexengine.state.action_manager import ActionManager
from hexengine.state.actions import PatchTitleBucket
from hexengine.state.game_state import BoardState, TurnState, UnitState

EXPECTED_ORDER = (
    AuthorityAttackPipelineStep.NORMALIZE_WIRE_AND_PARTIES,
    AuthorityAttackPipelineStep.HOOK_VALIDATE,
    AuthorityAttackPipelineStep.HOOK_RESOLVE,
    AuthorityAttackPipelineStep.REQUIRE_TITLE_EXTENSION_KEY,
    AuthorityAttackPipelineStep.COMMIT_ATTACK_AND_EFFECTS,
    AuthorityAttackPipelineStep.AFTER_ATTACK_APPLIED,
    AuthorityAttackPipelineStep.BROADCAST_COMBAT_EVENTS,
    AuthorityAttackPipelineStep.MAYBE_AUTO_ADVANCE_PHASE,
)


def test_authority_attack_pipeline_order_is_stable() -> None:
    assert AUTHORITY_ATTACK_PIPELINE == EXPECTED_ORDER
    assert len(AUTHORITY_ATTACK_PIPELINE) == 8


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

    async def _send_error(self, player_id: str, message: str) -> None:
        raise AssertionError(f"{player_id}: {message}")

    def _title_extension_key(self) -> str | None:
        return "testpack"

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
    return GameState(board=board, turn=turn, title_state={}, title_bucket_key="testpack")


def test_after_attack_applied_follow_ups_run_before_broadcast() -> None:
    st0 = _two_unit_combat_state()
    mgr = ActionManager(st0)
    marker = {"patch_applied": False}

    def validate(_ctx: AttackContext) -> None:
        return None

    def resolve(_ctx: AttackContext) -> AttackResolution:
        return AttackResolution(outcome="none")

    def after_applied(ctx: AfterAttackAppliedContext) -> list:
        marker["patch_applied"] = True
        return [
            PatchTitleBucket(
                ctx.extension_key,
                {"after_attack_hook": True},
            )
        ]

    host = _AttackHost(
        hooks=TitleHooks(
            attack=AttackHooks(
                validate_attack=validate,
                resolve_attack=resolve,
                after_attack_applied=after_applied,
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
                "attack_kind": "melee",
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
