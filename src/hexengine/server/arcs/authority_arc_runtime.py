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

from ...arcs import ArcSpec, begin_arc, read_arc_cursor, submit_event
from ...hooks.title import TitleHooks
from ...state import ActionManager
from ..protocol import ActionResult, Message, PlayerInfo


class ArcRuntimeHost(Protocol):
    """Minimal `GameServer` surface the arc runtime needs."""

    hooks: TitleHooks
    action_manager: ActionManager

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


__all__ = [
    "ArcRuntimeHost",
    "begin_combat_arc",
    "combat_arc_spec",
    "drive_combat_arc_event",
]
