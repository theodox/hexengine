"""
Engine stepwise movement as a declared arc (composable arcs, Phase 3).

Declares the stepwise movement FSM (continue / interrupt sub-arc) as data for the
generic runner. Segment `kind` values match the movement arc gate strings so the
declaration can be parity-checked against the legacy payload mirror.

Effects are supplied at runtime (see server.arcs.movement_arc_effects) because step
application needs modification hooks from the authoritative server host.

Mandatory retreats reuse this arc (``SEG_RETREAT_OPEN``): multi-hex retreat paths share
the same stepwise payload and continuation/interrupt machinery as long moves instead of
a separate retreat graph. Combat cleanup still owns retreat gates, obligations, and
final fulfillment; this arc only walks the committed polyline. Titles opt in once via
``ENGINE_MOVEMENT_ARC_PRESET``.

We accept cross-arc coupling: payload fields ``retreat_fulfillment`` and
``finalize_request`` hand back to the combat overlay when the path completes, and
path/stack validation in ``authority_movement`` runs before
``drive_movement_arc_retreat_open``. Single-hex retreats still use a plain ``MoveUnit``
without ``retreat_open``. Normal ``resolve_move_as_steps`` opens inline in authority
for now (not yet on this graph).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from ..hexes.types import Hex
from ..state import GameState
from ..state.action_manager import StateAction
from ..state.movement_arc import (
    HEXENGINE_MOVEMENT_ARC_KEY,
    MOVEMENT_ARC_GATE_AWAITING_CONTINUE,
    MOVEMENT_ARC_GATE_AWAITING_INTERRUPT,
)
from ..state.engine_session_state import engine_bucket
from .spec import ArcContext

MOVEMENT_ARC_ID = "movement"

SEG_CONTINUE = "continue"
SEG_RETREAT_OPEN = "retreat_open"
SEG_STEP_RESOLVE = "step_resolve"
SEG_INTERRUPT = "interrupt"
SEG_INTERRUPT_RESOLVE = "interrupt_resolve"

OWNER_MOVING = "moving"

Guard = Callable[[ArcContext], bool]
Effect = Callable[[ArcContext], list[StateAction]]


class MovementArcEffectsBinding(Protocol):
    """Host-bound guards and effects the movement arc declaration wires in."""

    def matches_stepwise_step(self, ctx: ArcContext) -> bool: ...

    def apply_step(self, ctx: ArcContext) -> list[StateAction]: ...

    def finish_path(self, ctx: ArcContext) -> list[StateAction]: ...

    def is_interrupt_responder(self, ctx: ArcContext) -> bool: ...

    def pass_interrupt(self, ctx: ArcContext) -> list[StateAction]: ...

    def matches_retreat_open(self, ctx: ArcContext) -> bool: ...

    def open_retreat_step(self, ctx: ArcContext) -> list[StateAction]: ...


def read_movement_payload(state: GameState) -> dict[str, Any] | None:
    """Return the movement arc payload from engine state, if any."""

    raw = engine_bucket(state, HEXENGINE_MOVEMENT_ARC_KEY)
    if not isinstance(raw, dict):
        return None
    return dict(raw)


def path_tuple_from_payload(payload: dict[str, Any]) -> tuple[Hex, ...]:
    """Parse `path` wire list from a movement arc payload into hex tuples."""

    raw = payload.get("path")
    if not isinstance(raw, list):
        return ()
    out: list[Hex] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        try:
            out.append(Hex(int(row["i"]), int(row["j"]), int(row["k"])))
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(out)


def resolve_moving_faction(key: str, state: GameState) -> str | None:
    """OwnerRefResolver for the movement arc (only knows the "moving" owner)."""

    if key != OWNER_MOVING:
        return None
    flow = read_movement_payload(state)
    if not flow:
        return None
    faction = str(flow.get("moving_faction", "")).strip()
    return faction or None


def _movement_flow(ctx: ArcContext) -> dict[str, Any] | None:
    return read_movement_payload(ctx.state)


def path_complete(ctx: ArcContext) -> bool:
    flow = _movement_flow(ctx)
    if not flow:
        return True
    path = path_tuple_from_payload(flow)
    idx = int(flow.get("step_index", -1))
    return not path or idx >= len(path) - 1


def step_opened_interrupts(ctx: ArcContext) -> bool:
    flow = _movement_flow(ctx)
    if not flow:
        return False
    queue = flow.get("interrupt_queue")
    return isinstance(queue, list) and len(queue) > 0


def interrupt_queue_empty(ctx: ArcContext) -> bool:
    flow = _movement_flow(ctx)
    if not flow:
        return True
    queue = flow.get("interrupt_queue")
    return not isinstance(queue, list) or not queue


__all__ = [
    "MOVEMENT_ARC_GATE_AWAITING_CONTINUE",
    "MOVEMENT_ARC_GATE_AWAITING_INTERRUPT",
    "MOVEMENT_ARC_ID",
    "OWNER_MOVING",
    "SEG_CONTINUE",
    "SEG_RETREAT_OPEN",
    "SEG_INTERRUPT",
    "SEG_INTERRUPT_RESOLVE",
    "SEG_STEP_RESOLVE",
    "MovementArcEffectsBinding",
    "interrupt_queue_empty",
    "path_complete",
    "path_tuple_from_payload",
    "read_movement_payload",
    "resolve_moving_faction",
    "step_opened_interrupts",
]
