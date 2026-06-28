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
from ...arcs.capabilities import arc_event_action_types
from ...arcs.title.lookup import (
    combat_arc_spec,
    lookup_arc_spec,
    movement_arc_spec_for_host,
    turn_arc_registry_from_hooks,
)
from ...arcs.movement_arc_decl import (
    MOVEMENT_ARC_ID,
    SEG_CONTINUE,
    SEG_INTERRUPT,
    SEG_RETREAT_OPEN,
    SEG_STEPWISE_OPEN,
    read_movement_payload,
)
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


class ArcDispatch(str, Enum):
    """Result of offering an RPC to the active overlay (interaction) arc."""

    NOT_DECLARED = "not_declared"
    HANDLED = "handled"
    NO_CURSOR = "no_cursor"
    REJECTED = "rejected"


class MovementArcDriveOutcome(str, Enum):
    """Result of offering a movement arc open RPC."""

    NOT_DECLARED = "not_declared"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


# Stable interaction-aftermath wire verbs (core mechanisms; titles gate via segments).
INTERACTION_AFTERMATH_WIRE_VERBS = frozenset(
    {
        "CombatAdvance",
        "CombatDeclineAdvance",
        "CombatDisruptInsteadOfRetreat",
    }
)


COMBAT_NO_CURSOR_MSG = "No active combat segment for this action"
COMBAT_REJECTED_MSG = "Action not allowed in the current combat segment"
COMBAT_ARC_REQUIRED_MSG = (
    "This title must declare ArcHook.COMBAT_ARC for combat cleanup actions"
)


def overlay_rpc_action_types(hooks: TitleHooks) -> frozenset[str]:
    """
    RPC names routed through the overlay arc before normal dispatch.

    When a title declares an interaction arc, every ``Event`` action type on that graph
    except ``Attack`` (authority attack pipeline) and ``MoveUnit`` (dedicated overlay
    move path) is eligible. When undeclared, only stable aftermath verbs are treated
    as overlay-only for error messaging.
    """

    spec = combat_arc_spec(hooks)
    if spec is None:
        return INTERACTION_AFTERMATH_WIRE_VERBS
    types = set(arc_event_action_types(spec.arc))
    types.discard("Attack")
    types.discard("MoveUnit")
    return frozenset(types)


def active_overlay_arc_cursor(state: GameState, hooks: TitleHooks) -> ArcCursor | None:
    """Active cursor when it points at the title's declared overlay (interaction) arc."""

    spec = combat_arc_spec(hooks)
    if spec is None:
        return None
    cur = read_arc_cursor(state)
    if cur is None or cur.arc_id != spec.arc.id:
        return None
    return cur


def title_declares_overlay_arc(hooks: TitleHooks) -> bool:
    return combat_arc_spec(hooks) is not None


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


def tear_down_movement_arc_after_retreat(host: ArcRuntimeHost) -> None:
    """Clear stepwise retreat payload once combat cleanup takes over."""

    from ...arcs.movement_arc_decl import read_movement_payload
    from ...state.actions import WriteHexengineMovementArc

    flow = read_movement_payload(host.action_manager.current_state)
    if not isinstance(flow, dict) or not flow.get("retreat_fulfillment"):
        return
    host.action_manager.execute(WriteHexengineMovementArc(None))
    sync_movement_cursor_from_payload(host)


def resume_combat_arc_after_retreat_fulfillment(host: ArcRuntimeHost) -> None:
    """Run combat ``resolve`` auto transitions after movement-arc retreat fulfillment.

    Movement-arc retreat completion clears obligations via the title binding but does not
    pass through the combat arc ``resolve`` segment, which normally offers advance.
    """

    from ...arcs.runner import _auto_advance
    from ...authoring.patterns.combat import SEG_RESOLVE

    tear_down_movement_arc_after_retreat(host)

    spec = combat_arc_spec(host.hooks)
    if spec is None:
        return
    arc = spec.arc
    host.action_manager.execute(
        SetArcCursor(ArcCursor(arc_id=arc.id, segment_id=SEG_RESOLVE))
    )
    _auto_advance(arc, host.action_manager, spec.owner_resolver)
    if read_arc_cursor(host.action_manager.current_state) is None:
        restore_routine_cursor(host)


def begin_combat_arc(host: ArcRuntimeHost) -> None:
    """Start the combat arc if the title declares one (no-op otherwise)."""

    spec = combat_arc_spec(host.hooks)
    if spec is None:
        return
    begin_arc(spec.arc, host.action_manager, resolver=spec.owner_resolver)
    if read_arc_cursor(host.action_manager.current_state) is None:
        restore_routine_cursor(host)


async def finish_arc_dispatch(
    host: ArcRuntimeHost,
    player_id: str,
    outcome: ArcDispatch,
    *,
    no_cursor_msg: str = COMBAT_NO_CURSOR_MSG,
    rejected_msg: str = COMBAT_REJECTED_MSG,
) -> bool:
    """
    Apply an overlay arc dispatch outcome.

    Returns True when the request is finished (success or error sent). False when the
    title declares no overlay arc and the caller should reject the cleanup RPC.
    """

    if outcome == ArcDispatch.HANDLED:
        return True
    if outcome == ArcDispatch.NOT_DECLARED:
        return False
    if outcome == ArcDispatch.NO_CURSOR:
        await host._send_error(player_id, no_cursor_msg)
    else:
        await host._send_error(player_id, rejected_msg)
    return True


async def try_arc_rpc(
    host: ArcRuntimeHost,
    player_id: str,
    player: PlayerInfo,
    action_type: str,
    params: dict[str, Any] | None = None,
) -> ArcDispatch:
    """
    Offer an RPC to the active overlay arc when the title declares one.

    Uses ``submit_event`` on the active segment; rejects when no overlay cursor is set
    or the segment denies the action type.
    """

    if not title_declares_overlay_arc(host.hooks):
        return ArcDispatch.NOT_DECLARED
    if active_overlay_arc_cursor(host.action_manager.current_state, host.hooks) is None:
        return ArcDispatch.NO_CURSOR
    if await drive_overlay_arc_event(host, player_id, player, action_type, params):
        return ArcDispatch.HANDLED
    return ArcDispatch.REJECTED


async def try_arc_move_unit(
    host: ArcRuntimeHost,
    player_id: str,
    player: PlayerInfo,
    params: dict[str, Any],
    *,
    is_retreat_fulfillment: bool,
    is_advance_fulfillment: bool,
) -> ArcDispatch:
    """
    Offer ``MoveUnit`` to the overlay arc when the cursor is on an interaction segment.

    Routine moves during a non-overlay cursor return ``NOT_DECLARED`` so normal movement
    dispatch proceeds. Retreat/advance fulfillment without an overlay cursor returns
    ``NO_CURSOR``.
    """

    if not title_declares_overlay_arc(host.hooks):
        return ArcDispatch.NOT_DECLARED

    flow = read_movement_payload(host.action_manager.current_state)
    if isinstance(flow, dict) and flow.get("retreat_fulfillment"):
        return ArcDispatch.NOT_DECLARED

    wire_path = params.get("path")
    if is_retreat_fulfillment and isinstance(wire_path, list) and len(wire_path) >= 2:
        return ArcDispatch.NOT_DECLARED

    cur = active_overlay_arc_cursor(host.action_manager.current_state, host.hooks)
    if cur is None:
        if is_retreat_fulfillment or is_advance_fulfillment:
            return ArcDispatch.NO_CURSOR
        return ArcDispatch.NOT_DECLARED

    spec = combat_arc_spec(host.hooks)
    if spec is not None:
        try:
            segment = spec.arc.get(cur.segment_id)
        except KeyError:
            segment = None
        if segment is not None and "MoveUnit" not in segment.allowed_actions:
            return ArcDispatch.REJECTED

    if await drive_overlay_arc_event(host, player_id, player, "MoveUnit", params):
        return ArcDispatch.HANDLED
    return ArcDispatch.REJECTED


async def drive_overlay_arc_event(
    host: ArcRuntimeHost,
    player_id: str,
    player: PlayerInfo,
    action_type: str,
    params: dict[str, Any] | None = None,
) -> bool:
    """Offer one RPC to the active overlay (interaction) arc."""

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

    return movement_arc_spec_for_host(host)


def sync_movement_cursor_from_payload(host: ArcRuntimeHost) -> None:
    """Align the generic arc cursor with the movement payload gate mirror.

    Stepwise paths open via the movement arc ``stepwise_open`` segment (normal
    ``resolve_move_as_steps``) or ``retreat_open`` (``drive_movement_arc_retreat_open``).
    This function sets ``SetArcCursor`` to the interrupt or continue segment so ``drive_movement_arc_event``
    can dispatch ``PassMovementInterrupt`` and continuation ``MoveUnit`` RPCs.
    """

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


async def drive_movement_arc_retreat_open(
    host: ArcRuntimeHost,
    player_id: str,
    player: PlayerInfo,
    params: dict[str, Any],
) -> MovementArcDriveOutcome:
    """Open a mandatory retreat path via the movement arc ``retreat_open`` segment."""

    spec = movement_arc_spec(host)
    if spec is None:
        return MovementArcDriveOutcome.NOT_DECLARED

    host.action_manager.execute(
        SetArcCursor(
            ArcCursor(arc_id=MOVEMENT_ARC_ID, segment_id=SEG_RETREAT_OPEN)
        )
    )
    result = submit_event(
        spec.arc,
        host.action_manager,
        action_type="MoveUnit",
        actor=str(player.faction),
        params=dict(params),
        resolver=spec.owner_resolver,
    )
    if not result.ok:
        host.action_manager.execute(SetArcCursor(None))
        restore_routine_cursor(host)
        await host._send_error(
            player_id, "Movement arc rejected retreat path open"
        )
        return MovementArcDriveOutcome.REJECTED

    sync_movement_cursor_from_payload(host)
    ok = ActionResult(success=True, action_id=str(uuid.uuid4()))
    await host._send_message(player_id, ok.to_message())
    await host._broadcast_state_update()
    return MovementArcDriveOutcome.ACCEPTED


async def drive_movement_arc_stepwise_open(
    host: ArcRuntimeHost,
    player_id: str,
    player: PlayerInfo,
    params: dict[str, Any],
) -> MovementArcDriveOutcome:
    """Open a normal stepwise move via the movement arc ``stepwise_open`` segment."""

    spec = movement_arc_spec(host)
    if spec is None:
        return MovementArcDriveOutcome.NOT_DECLARED

    host.action_manager.execute(
        SetArcCursor(
            ArcCursor(arc_id=MOVEMENT_ARC_ID, segment_id=SEG_STEPWISE_OPEN)
        )
    )
    result = submit_event(
        spec.arc,
        host.action_manager,
        action_type="MoveUnit",
        actor=str(player.faction),
        params=dict(params),
        resolver=spec.owner_resolver,
    )
    if not result.ok:
        host.action_manager.execute(SetArcCursor(None))
        restore_routine_cursor(host)
        await host._send_error(
            player_id, "Movement arc rejected stepwise open"
        )
        return MovementArcDriveOutcome.REJECTED

    sync_movement_cursor_from_payload(host)
    ok = ActionResult(success=True, action_id=str(uuid.uuid4()))
    await host._send_message(player_id, ok.to_message())
    await host._broadcast_state_update()
    return MovementArcDriveOutcome.ACCEPTED


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

    from ...arcs.title.schedule import next_phase_from_registry

    reg = turn_arc_registry_from_hooks(host.hooks)
    if reg is None:
        return None
    return next_phase_from_registry(
        reg, int(host.action_manager.current_state.turn.schedule_index)
    )


__all__ = [
    "ArcDispatch",
    "ArcRuntimeHost",
    "COMBAT_ARC_REQUIRED_MSG",
    "COMBAT_NO_CURSOR_MSG",
    "COMBAT_REJECTED_MSG",
    "INTERACTION_AFTERMATH_WIRE_VERBS",
    "MovementArcDriveOutcome",
    "active_overlay_arc_cursor",
    "begin_combat_arc",
    "begin_routine_slot",
    "combat_arc_spec",
    "drive_movement_arc_event",
    "drive_movement_arc_retreat_open",
    "drive_movement_arc_stepwise_open",
    "drive_overlay_arc_event",
    "finish_arc_dispatch",
    "lookup_arc_spec",
    "movement_arc_spec",
    "overlay_rpc_action_types",
    "resolve_active_segment_owner",
    "restore_routine_cursor",
    "resume_combat_arc_after_retreat_fulfillment",
    "schedule_next_phase_info",
    "sync_movement_cursor_from_payload",
    "tear_down_movement_arc_after_retreat",
    "title_declares_overlay_arc",
    "try_arc_move_unit",
    "try_arc_rpc",
    "turn_arc_registry_from_hooks",
]
