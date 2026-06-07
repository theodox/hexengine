"""
Engine-side bridge between the async server and the generic arc runner.

The server stays title-agnostic: it asks the title (via the `arcs` hook bundle) for the
declared arc + owner resolver, then drives the runner. Phase 4 adds the turn arc registry
(schedule + routine phase arcs) and restores the routine cursor when overlay arcs finish.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Protocol

from ...hooks.core import ENGINE_DEFAULT
from ...arcs import (
    ArcCursor,
    ArcSpec,
    SetArcCursor,
    SuspendedFrame,
    begin_arc,
    read_arc_cursor,
    resolve_owner,
    submit_event,
)
from ...arcs.movement_arc_decl import (
    MOVEMENT_ARC_ID,
    SEG_CONTINUE,
    SEG_INTERRUPT,
    read_movement_payload,
)
from ...arcs.registry import TurnArcRegistry
from ...hooks.title import TitleHooks
from ...state import ActionManager, GameState
from ...state.movement_arc import MOVEMENT_ARC_GATE_AWAITING_INTERRUPT
from ..protocol import ActionResult, Message, PlayerInfo


class ArcRuntimeHost(Protocol):
    """Minimal `GameServer` surface the arc runtime needs."""

    hooks: TitleHooks
    action_manager: ActionManager

    def movement_arc_spec(self) -> ArcSpec | None: ...

    async def _send_message(self, player_id: str, message: Message) -> None: ...

    async def _send_error(self, player_id: str, message: str) -> None: ...

    async def _broadcast_state_update(self) -> None: ...


class CombatArcDispatch(str, Enum):
    """Result of offering an RPC to the declared combat arc."""

    NOT_DECLARED = "not_declared"
    HANDLED = "handled"
    NO_CURSOR = "no_cursor"
    REJECTED = "rejected"


COMBAT_NO_CURSOR_MSG = "No active combat segment for this action"
COMBAT_REJECTED_MSG = "Action not allowed in the current combat segment"
COMBAT_ARC_REQUIRED_MSG = (
    "This title must declare ArcHook.COMBAT_ARC for combat cleanup actions"
)


def active_combat_arc_cursor(
    state: GameState, hooks: TitleHooks
) -> ArcCursor | None:
    """Active cursor when it points at the title's declared combat arc."""

    spec = combat_arc_spec(hooks)
    if spec is None:
        return None
    cur = read_arc_cursor(state)
    if cur is None or cur.arc_id != spec.arc.id:
        return None
    return cur


def title_declares_combat_arc(hooks: TitleHooks) -> bool:
    return combat_arc_spec(hooks) is not None


def turn_arc_registry_from_hooks(hooks: TitleHooks) -> TurnArcRegistry | None:
    """The title's turn arc registry, or None when not declared."""

    raw = hooks.arcs.turn_arc_registry_spec()
    return raw if isinstance(raw, TurnArcRegistry) else None


def lookup_arc_spec(host: ArcRuntimeHost, arc_id: str) -> ArcSpec | None:
    """Resolve any declared arc by id (routine, combat, movement)."""

    reg = turn_arc_registry_from_hooks(host.hooks)
    if reg is not None:
        spec = reg.routine_specs.get(str(arc_id))
        if spec is not None:
            return spec

    combat = combat_arc_spec(host.hooks)
    if combat is not None and combat.arc.id == arc_id:
        return combat

    movement = movement_arc_spec(host)
    if movement is not None and movement.arc.id == arc_id:
        return movement

    return None


def resolve_active_segment_owner(host: ArcRuntimeHost, state: GameState) -> str | None:
    """Resolved owner faction for the active arc segment, or routine current faction."""

    cursor = read_arc_cursor(state)
    if cursor is None:
        return str(state.turn.current_faction)

    spec = lookup_arc_spec(host, cursor.arc_id)
    if spec is None:
        return str(state.turn.current_faction)

    try:
        segment = spec.arc.get(cursor.segment_id)
    except KeyError:
        return str(state.turn.current_faction)

    owner = resolve_owner(segment.owner, state, spec.owner_resolver)
    if owner is None:
        return str(state.turn.current_faction)
    return str(owner)


def begin_routine_slot(host: ArcRuntimeHost, schedule_index: int) -> None:
    """Place the cursor on the routine arc for `schedule_index` (no-op without registry)."""

    reg = turn_arc_registry_from_hooks(host.hooks)
    if reg is None:
        return
    slot = reg.schedule.slot_at(schedule_index)
    spec = reg.routine_specs.get(slot.routine_arc_id)
    if spec is None:
        return
    begin_arc(spec.arc, host.action_manager, resolver=spec.owner_resolver)


def restore_routine_cursor(host: ArcRuntimeHost) -> None:
    """Re-open the routine arc for the current schedule slot when no overlay arc is active."""

    if read_arc_cursor(host.action_manager.current_state) is not None:
        return
    idx = int(host.action_manager.current_state.turn.schedule_index)
    begin_routine_slot(host, idx)


def combat_arc_spec(hooks: TitleHooks) -> ArcSpec | None:
    """The title's declared combat arc bundle, or None when it declares no arc."""

    raw = hooks.arcs.combat_arc_spec()
    return raw if isinstance(raw, ArcSpec) else None


def begin_combat_arc(host: ArcRuntimeHost) -> None:
    """Start the combat arc if the title declares one (no-op otherwise)."""

    spec = combat_arc_spec(host.hooks)
    if spec is None:
        return
    begin_arc(spec.arc, host.action_manager, resolver=spec.owner_resolver)
    if read_arc_cursor(host.action_manager.current_state) is None:
        restore_routine_cursor(host)


async def finish_combat_arc_dispatch(
    host: ArcRuntimeHost,
    player_id: str,
    outcome: CombatArcDispatch,
    *,
    no_cursor_msg: str = COMBAT_NO_CURSOR_MSG,
    rejected_msg: str = COMBAT_REJECTED_MSG,
) -> bool:
    """
    Apply a combat dispatch outcome.

    Returns True when the request is finished (success or error sent). False when the
    title declares no combat arc and the caller should reject the combat cleanup RPC.
    """

    if outcome == CombatArcDispatch.HANDLED:
        return True
    if outcome == CombatArcDispatch.NOT_DECLARED:
        return False
    if outcome == CombatArcDispatch.NO_CURSOR:
        await host._send_error(player_id, no_cursor_msg)
    else:
        await host._send_error(player_id, rejected_msg)
    return True


async def try_combat_arc_rpc(
    host: ArcRuntimeHost,
    player_id: str,
    player: PlayerInfo,
    action_type: str,
    params: dict[str, Any] | None = None,
) -> CombatArcDispatch:
    """Offer a dedicated combat RPC to the declared arc (no legacy fallback)."""

    if not title_declares_combat_arc(host.hooks):
        return CombatArcDispatch.NOT_DECLARED
    if active_combat_arc_cursor(host.action_manager.current_state, host.hooks) is None:
        return CombatArcDispatch.NO_CURSOR
    if await drive_combat_arc_event(
        host, player_id, player, action_type, params
    ):
        return CombatArcDispatch.HANDLED
    return CombatArcDispatch.REJECTED


async def try_combat_arc_move_unit(
    host: ArcRuntimeHost,
    player_id: str,
    player: PlayerInfo,
    params: dict[str, Any],
    *,
    is_retreat_fulfillment: bool,
    is_advance_fulfillment: bool,
) -> CombatArcDispatch:
    """
    Offer ``MoveUnit`` to the combat arc when appropriate.

    Routine moves during a non-combat cursor return ``NOT_DECLARED`` so normal
    movement dispatch can proceed. Retreat/advance fulfillment without a combat
    cursor returns ``NO_CURSOR``.
    """

    if not title_declares_combat_arc(host.hooks):
        return CombatArcDispatch.NOT_DECLARED

    flow = read_movement_payload(host.action_manager.current_state)
    if isinstance(flow, dict) and flow.get("retreat_fulfillment"):
        return CombatArcDispatch.NOT_DECLARED

    wire_path = params.get("path")
    if (
        is_retreat_fulfillment
        and isinstance(wire_path, list)
        and len(wire_path) > 2
    ):
        return CombatArcDispatch.NOT_DECLARED

    cur = active_combat_arc_cursor(host.action_manager.current_state, host.hooks)
    if cur is None:
        if is_retreat_fulfillment or is_advance_fulfillment:
            return CombatArcDispatch.NO_CURSOR
        return CombatArcDispatch.NOT_DECLARED
    if await drive_combat_arc_event(host, player_id, player, "MoveUnit", params):
        return CombatArcDispatch.HANDLED
    return CombatArcDispatch.REJECTED


async def drive_combat_arc_event(
    host: ArcRuntimeHost,
    player_id: str,
    player: PlayerInfo,
    action_type: str,
    params: dict[str, Any] | None = None,
) -> bool:
    """Offer one RPC to the active combat arc."""

    spec = combat_arc_spec(host.hooks)
    if spec is None:
        return False
    cursor = read_arc_cursor(host.action_manager.current_state)
    if cursor is None or cursor.arc_id != spec.arc.id:
        return False

    result = submit_event(
        spec.arc,
        host.action_manager,
        action_type=action_type,
        actor=str(player.faction),
        params=params,
        resolver=spec.owner_resolver,
    )
    if not result.ok:
        return False

    if read_arc_cursor(host.action_manager.current_state) is None:
        restore_routine_cursor(host)

    ok = ActionResult(success=True, action_id=str(uuid.uuid4()))
    await host._send_message(player_id, ok.to_message())
    await host._broadcast_state_update()
    return True


def movement_arc_spec(host: ArcRuntimeHost) -> ArcSpec | None:
    """The engine/title movement arc bundle, or None when unavailable."""

    raw = host.hooks.arcs.movement_arc_spec()
    if isinstance(raw, ArcSpec):
        return raw
    if raw is not ENGINE_DEFAULT:
        return None
    return host.movement_arc_spec()


def sync_movement_cursor_from_payload(host: ArcRuntimeHost) -> None:
    """Keep the generic arc cursor aligned with the movement payload gate mirror."""

    spec = movement_arc_spec(host)
    if spec is None:
        return
    flow = read_movement_payload(host.action_manager.current_state)
    if not flow:
        host.action_manager.execute(SetArcCursor(None))
        restore_routine_cursor(host)
        return

    gate = str(flow.get("gate", ""))
    if gate == MOVEMENT_ARC_GATE_AWAITING_INTERRUPT:
        host.action_manager.execute(
            SetArcCursor(
                ArcCursor(
                    arc_id=MOVEMENT_ARC_ID,
                    segment_id=SEG_INTERRUPT,
                    suspended=SuspendedFrame(resume_segment_id=SEG_CONTINUE),
                )
            )
        )
        return

    host.action_manager.execute(
        SetArcCursor(ArcCursor(arc_id=MOVEMENT_ARC_ID, segment_id=SEG_CONTINUE))
    )


def begin_movement_arc(host: ArcRuntimeHost) -> None:
    """Start the movement arc cursor when a stepwise path opens (no-op without spec)."""

    spec = movement_arc_spec(host)
    if spec is None:
        return
    begin_arc(spec.arc, host.action_manager, resolver=spec.owner_resolver)


async def drive_movement_arc_event(
    host: ArcRuntimeHost,
    player_id: str,
    player: PlayerInfo,
    action_type: str,
    params: dict[str, Any] | None = None,
) -> bool:
    """Offer one RPC to the active movement arc."""

    spec = movement_arc_spec(host)
    if spec is None:
        return False
    cursor = read_arc_cursor(host.action_manager.current_state)
    if cursor is None or cursor.arc_id != spec.arc.id:
        return False

    result = submit_event(
        spec.arc,
        host.action_manager,
        action_type=action_type,
        actor=str(player.faction),
        params=params,
        resolver=spec.owner_resolver,
    )
    if not result.ok:
        return False

    sync_movement_cursor_from_payload(host)

    ok = ActionResult(success=True, action_id=str(uuid.uuid4()))
    await host._send_message(player_id, ok.to_message())
    await host._broadcast_state_update()
    return True


def schedule_next_phase_info(host: ArcRuntimeHost) -> dict[str, Any] | None:
    """Next schedule slot from the declared arc schedule, or None when undeclared."""

    reg = turn_arc_registry_from_hooks(host.hooks)
    if reg is None:
        return None
    slot, next_idx = reg.schedule.next_after(
        host.action_manager.current_state.turn.schedule_index
    )
    return {
        "faction": slot.faction,
        "phase": slot.phase,
        "max_actions": int(slot.max_actions),
        "schedule_index": next_idx,
    }


__all__ = [
    "ArcRuntimeHost",
    "COMBAT_ARC_REQUIRED_MSG",
    "COMBAT_NO_CURSOR_MSG",
    "COMBAT_REJECTED_MSG",
    "CombatArcDispatch",
    "active_combat_arc_cursor",
    "begin_combat_arc",
    "begin_movement_arc",
    "begin_routine_slot",
    "combat_arc_spec",
    "drive_combat_arc_event",
    "drive_movement_arc_event",
    "finish_combat_arc_dispatch",
    "lookup_arc_spec",
    "movement_arc_spec",
    "resolve_active_segment_owner",
    "restore_routine_cursor",
    "schedule_next_phase_info",
    "sync_movement_cursor_from_payload",
    "title_declares_combat_arc",
    "try_combat_arc_move_unit",
    "try_combat_arc_rpc",
    "turn_arc_registry_from_hooks",
]
