"""
Authority-side `Attack` request pipeline (server → hooks → state → broadcast).

This module names the **ordered steps** the engine runs for a single client
`Attack` action. Related **cleanup** interactions (mandatory retreat moves, disrupt-instead,
combat advance) are implemented in `hexengine.server.arcs.authority_combat_cleanup`. Stepwise
movement is `hexengine.server.arcs.authority_movement`; together with this file they form
three server-side **arcs** (vocabulary in `hexengine.state.movement_arc`).

Titles customize behavior via `TitleHooks.attack` (validate / resolve / auto-advance);
this file is the stable **orchestration** surface for authors reading the engine.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any, Protocol

from ...arcs import ArcCursor, SetArcCursor, read_arc_cursor, submit_event
from ...arcs.segment_wire import segment_denies_action_for_faction
from ...authoring.patterns.combat import SEG_ATTACK
from ...hooks.title import TitleHooks
from ...state import GameState
from ...state.action_manager import ActionManager
from .authority_arc_runtime import combat_arc_spec, restore_routine_cursor
from .authority_attack_commit import build_attack_context_from_wire
from .authority_attack_wire import (
    dedupe_wire_id_list,
    normalize_attack_party_ids,
    optional_wire_hex_frozenset,
    sorted_unique_hexes_from_unit_ids,
)

ATTACK_REQUIRES_COMBAT_ARC_MSG = (
    "This game title does not declare a combat arc Attack segment"
)


class AuthorityAttackPipelineStep(StrEnum):
    """Named **segments** of one authority `Attack` RPC within the combat **arc**."""

    NORMALIZE_WIRE_AND_PARTIES = "normalize_wire_and_parties"
    SUBMIT_ATTACK_EVENT = "submit_attack_event"
    BROADCAST_COMBAT_EVENTS = "broadcast_combat_events"
    MAYBE_AUTO_ADVANCE_PHASE = "maybe_auto_advance_phase"


ATTACK_BLOCKED_BY_ACTIVE_SEGMENT_MSG = (
    "Resolve combat obligations before issuing another attack"
)


AUTHORITY_ATTACK_PIPELINE: tuple[AuthorityAttackPipelineStep, ...] = (
    AuthorityAttackPipelineStep.NORMALIZE_WIRE_AND_PARTIES,
    AuthorityAttackPipelineStep.SUBMIT_ATTACK_EVENT,
    AuthorityAttackPipelineStep.BROADCAST_COMBAT_EVENTS,
    AuthorityAttackPipelineStep.MAYBE_AUTO_ADVANCE_PHASE,
)


def _combat_arc_supports_attack_event(host: AuthorityAttackHost) -> bool:
    spec = combat_arc_spec(host.hooks)
    if spec is None:
        return False
    try:
        spec.arc.get(SEG_ATTACK)
    except KeyError:
        return False
    return True


def _attack_submit_error_message(reason: str) -> str:
    if "not allowed" in reason:
        return ATTACK_BLOCKED_BY_ACTIVE_SEGMENT_MSG
    if "not segment owner" in reason:
        return "Not your turn for this attack"
    return reason or "Attack rejected"


class AuthorityAttackHost(Protocol):
    """Minimal `GameServer` surface used by `execute_authority_attack_request`."""

    hooks: TitleHooks
    action_manager: ActionManager
    logger: logging.Logger

    async def _send_error(self, player_id: str, message: str) -> None: ...

    def _engine_session_state_key(self) -> str | None: ...

    async def _broadcast_combat_events(self, state: GameState) -> None: ...

    def lookup_arc_spec(self, arc_id: str) -> object: ...

    def _get_next_phase(self) -> dict[str, Any]: ...

    def _after_next_phase_applied(self) -> None: ...

    def _maybe_auto_advance_phase(
        self,
        raw: bool | object,
        *,
        catalog_path: str | None,
        log_reason: str,
    ) -> bool: ...


async def _execute_arc_attack(
    host: AuthorityAttackHost,
    *,
    player_id: str,
    player_faction: str,
    current_state: GameState,
    params: dict[str, Any],
) -> bool:
    """Route ``Attack`` through the declared combat arc ``attack`` segment."""

    spec = combat_arc_spec(host.hooks)
    if spec is None:
        raise RuntimeError("combat arc spec missing")

    prior_cursor = read_arc_cursor(current_state)

    try:
        build_attack_context_from_wire(current_state, player_faction, params)
        if host._engine_session_state_key():
            if segment_denies_action_for_faction(
                host, current_state, player_faction, "Attack"
            ):
                raise ValueError(ATTACK_BLOCKED_BY_ACTIVE_SEGMENT_MSG)
        if not host._engine_session_state_key():
            raise ValueError(
                "This game title does not define a state extension key for combat"
            )
    except Exception as e:
        await host._send_error(player_id, str(e))
        return False

    host.action_manager.execute(
        SetArcCursor(
            ArcCursor(arc_id=spec.arc.id, segment_id=SEG_ATTACK),
        )
    )

    try:
        result = submit_event(
            spec.arc,
            host.action_manager,
            action_type="Attack",
            actor=player_faction,
            params=dict(params),
            resolver=spec.owner_resolver,
        )
    except Exception as e:
        if prior_cursor is not None:
            host.action_manager.execute(SetArcCursor(prior_cursor))
        else:
            restore_routine_cursor(host)
        await host._send_error(player_id, f"Action failed: {e}")
        return False

    if not result.ok:
        if prior_cursor is not None:
            host.action_manager.execute(SetArcCursor(prior_cursor))
        else:
            restore_routine_cursor(host)
        await host._send_error(
            player_id, _attack_submit_error_message(str(result.reason or ""))
        )
        return False

    if read_arc_cursor(host.action_manager.current_state) is None:
        restore_routine_cursor(host)

    return True


async def execute_authority_attack_request(
    host: AuthorityAttackHost,
    *,
    player_id: str,
    player_faction: str,
    current_state: GameState,
    params: dict[str, Any],
) -> bool:
    """
    Run the authority pipeline for one `Attack` client request.

    Returns:
        True if the attack was committed and the caller should send success + state
        broadcast. False if an error was already sent to the player.
    """
    if not _combat_arc_supports_attack_event(host):
        await host._send_error(player_id, ATTACK_REQUIRES_COMBAT_ARC_MSG)
        return False

    ok = await _execute_arc_attack(
        host,
        player_id=player_id,
        player_faction=player_faction,
        current_state=current_state,
        params=params,
    )

    if not ok:
        return False

    st_after = host.action_manager.current_state
    await host._broadcast_combat_events(st_after)

    adv = host.hooks.attack.auto_advance(st_after)
    host._maybe_auto_advance_phase(
        adv,
        catalog_path=None,
        log_reason=(
            f"after attack ({st_after.turn.current_faction} "
            f"{st_after.turn.current_phase})"
        ),
    )

    return True


__all__ = [
    "ATTACK_BLOCKED_BY_ACTIVE_SEGMENT_MSG",
    "ATTACK_REQUIRES_COMBAT_ARC_MSG",
    "AUTHORITY_ATTACK_PIPELINE",
    "AuthorityAttackHost",
    "AuthorityAttackPipelineStep",
    "dedupe_wire_id_list",
    "execute_authority_attack_request",
    "normalize_attack_party_ids",
    "optional_wire_hex_frozenset",
    "sorted_unique_hexes_from_unit_ids",
]
