"""
Engine-side bridge between the async server and the generic arc runner.

The server stays title-agnostic: it asks the title (via the `arcs` hook bundle) for the
declared arc + owner resolver, then drives the runner. Phase 2 wires the single combat
arc; later phases generalize this into the full turn-arc registry.

Routing model (Phase 2c): retreat-fulfillment ``MoveUnit`` (direct and stepwise-path
completion) is offered to the runner the same way as disrupt/advance RPCs. The runner is
authoritative only when it *accepts* the event; on rejection the caller falls back to the
legacy handler. Stacked-retreat validation (``validate_retreat_fulfillment_stack``) stays
a server pre-guard run before the arc attempt.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from ...hooks.core import ENGINE_DEFAULT
from ...arcs import ArcSpec, ArcCursor, SuspendedFrame, SetArcCursor, begin_arc, read_arc_cursor, submit_event
from ...arcs.movement_arc_decl import (
    MOVEMENT_ARC_ID,
    SEG_CONTINUE,
    SEG_INTERRUPT,
    read_movement_payload,
    resolve_moving_faction,
)
from ...state.movement_arc import MOVEMENT_ARC_GATE_AWAITING_INTERRUPT
from ...hooks.title import TitleHooks
from ...state import ActionManager
from ..protocol import ActionResult, Message, PlayerInfo


class ArcRuntimeHost(Protocol):
    """Minimal `GameServer` surface the arc runtime needs."""

    hooks: TitleHooks
    action_manager: ActionManager

    def movement_arc_spec(self) -> ArcSpec | None: ...

    async def _send_message(self, player_id: str, message: Message) -> None: ...

    async def _broadcast_state_update(self) -> None: ...


def combat_arc_spec(hooks: TitleHooks) -> ArcSpec | None:
    """The title's declared combat arc bundle, or None when it declares no arc."""

    raw = hooks.arcs.combat_arc_spec()
    return raw if isinstance(raw, ArcSpec) else None


def begin_combat_arc(host: ArcRuntimeHost) -> None:
    """Start the combat arc if the title declares one (no-op otherwise).

    The arc's entry segment classifies the just-set combat state and auto-advances to the
    matching gate (or finishes immediately when there is no cleanup to do).
    """

    spec = combat_arc_spec(host.hooks)
    if spec is None:
        return
    begin_arc(spec.arc, host.action_manager, resolver=spec.owner_resolver)


async def drive_combat_arc_event(
    host: ArcRuntimeHost,
    player_id: str,
    player: PlayerInfo,
    action_type: str,
    params: dict[str, Any] | None = None,
) -> bool:
    """Offer one RPC to the active combat arc.

    Returns True only when the runner *accepts* the event: it ran the title effect,
    advanced the cursor, and replied to the client. Returns False on any rejection (no
    declared arc, no/stale active arc, wrong owner, or disallowed action) so the caller
    can fall back to the legacy handler. The runner never mutates state on rejection.
    """

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
    """Offer one RPC to the active movement arc (same accept/reject contract as combat)."""

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


__all__ = [
    "ArcRuntimeHost",
    "begin_combat_arc",
    "begin_movement_arc",
    "combat_arc_spec",
    "drive_combat_arc_event",
    "drive_movement_arc_event",
    "movement_arc_spec",
    "sync_movement_cursor_from_payload",
]
