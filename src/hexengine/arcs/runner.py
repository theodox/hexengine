"""
Generic arc runner: the single engine mechanism that drives any declared arc.

Given a declared Arc (spec.py) and the serialized cursor (cursor.py) it: resolves the
current segment, gates an incoming event by the segment's owner and allowed_actions,
picks the first transition whose guard passes, runs that transition's effect, moves the
cursor (advance / suspend / resume / finish), and then auto-drives any ownerless
segments until it rests on an owned segment (or the arc finishes).

The engine reads no title shapes. The only title-specific inputs are callables the title
supplies in the spec: transition guards/effects and an owner resolver for OwnerRef. The
runner invokes them but never inspects title bucket contents itself.

All mutation goes through an ActionSink (ActionManager satisfies it). Each StateAction is
executed exactly once, so undo/redo, snapshots, and the rng_log stay consistent — there
is no dry-run pass that would double-apply effects.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from .cursor import ArcCursor, SetArcCursor, read_arc_cursor
from .spec import (
    Arc,
    ArcContext,
    Event,
    Faction,
    FlowEnd,
    Goto,
    Interrupt,
    Owner,
    OwnerRef,
    OwnerScope,
    Target,
    Transition,
)

if TYPE_CHECKING:
    from ..state.action_manager import StateAction
    from ..state.game_state import GameState

# Resolves an OwnerRef key to a concrete faction (or None) from current state. Supplied
# by the title; the engine never interprets the key itself.
OwnerRefResolver = Callable[[str, "GameState"], "str | None"]

# Safety cap: a mis-declared automatic segment that loops would otherwise spin forever.
_MAX_AUTO_STEPS = 256


class ActionSink(Protocol):
    """The mutation gateway the runner drives (ActionManager satisfies this)."""

    @property
    def current_state(self) -> GameState: ...

    def execute(self, action: StateAction) -> GameState: ...


@dataclass(frozen=True)
class RunResult:
    """Outcome of feeding one event to the runner.

    ok is False for a legality rejection (no state changed); reason explains why.
    Authoring bugs (stuck/looping automatic segments) raise instead of returning here.
    """

    ok: bool
    state: GameState
    reason: str = ""


def resolve_owner(
    owner: Owner, state: GameState, resolver: OwnerRefResolver | None
) -> str | None:
    """Resolve a segment owner to a faction (None for ownerless/unresolved)."""

    if owner is OwnerScope.CURRENT:
        return state.turn.current_faction
    if owner is OwnerScope.NO_OWNER:
        return None
    if isinstance(owner, Faction):
        return owner.name
    if isinstance(owner, OwnerRef):
        if resolver is None:
            raise ValueError(f"owner {owner!r} needs an owner resolver")
        return resolver(owner.key, state)
    raise TypeError(f"unknown owner {owner!r}")


def _next_cursor(cursor: ArcCursor, target: Target) -> ArcCursor | None:
    """The cursor after taking target (None means the arc is finished)."""

    if isinstance(target, Goto):
        return cursor.advanced_to(target.segment)
    if isinstance(target, Interrupt):
        return cursor.suspended_into(target.segment, target.resume)
    if target is FlowEnd.RESUME:
        return cursor.resumed()
    if target is FlowEnd.DONE:
        return None
    raise TypeError(f"unknown target {target!r}")


def _first_passing(
    transitions: tuple[Transition, ...],
    ctx: ArcContext,
    *,
    action_type: str | None,
) -> Transition | None:
    """First transition matching the trigger (when action_type given) with a passing guard."""

    for t in transitions:
        if action_type is not None:
            if not (isinstance(t.trigger, Event) and t.trigger.action_type == action_type):
                continue
        if t.guard is None or t.guard(ctx):
            return t
    return None


def _apply_transition(
    sink: ActionSink,
    cursor: ArcCursor,
    transition: Transition,
    *,
    owner_faction: str | None,
    params: dict[str, Any],
) -> None:
    """Run the transition effect (if any), then move the cursor. One execute per action."""

    state = sink.current_state
    if transition.effect is not None:
        ctx = ArcContext(
            state=state,
            extension_key=state.title_bucket_key,
            owner_faction=owner_faction,
            params=params,
        )
        for action in transition.effect(ctx):
            sink.execute(action)
    sink.execute(SetArcCursor(_next_cursor(cursor, transition.target)))


def _auto_advance(
    arc: Arc, sink: ActionSink, resolver: OwnerRefResolver | None
) -> GameState:
    """Fire automatic transitions until the cursor rests on an owned segment or clears."""

    for _ in range(_MAX_AUTO_STEPS):
        state = sink.current_state
        cursor = read_arc_cursor(state)
        if cursor is None:
            return state
        segment = arc.get(cursor.segment_id)
        if not segment.is_automatic:
            return state
        ctx = ArcContext(
            state=state,
            extension_key=state.title_bucket_key,
            owner_faction=None,
            params={},
        )
        transition = _first_passing(segment.transitions, ctx, action_type=None)
        if transition is None:
            raise RuntimeError(
                f"automatic segment {arc.id}.{segment.id} has no firable transition "
                f"(all guards failed)"
            )
        _apply_transition(
            sink, cursor, transition, owner_faction=None, params={}
        )
    raise RuntimeError(
        f"arc {arc.id!r} exceeded {_MAX_AUTO_STEPS} automatic steps (declared loop?)"
    )


def begin_arc(
    arc: Arc, sink: ActionSink, *, resolver: OwnerRefResolver | None = None
) -> GameState:
    """Start arc: set the cursor to its entry, then auto-advance leading automatic steps."""

    arc.validate()
    sink.execute(SetArcCursor(ArcCursor(arc_id=arc.id, segment_id=arc.entry)))
    return _auto_advance(arc, sink, resolver)


def submit_event(
    arc: Arc,
    sink: ActionSink,
    *,
    action_type: str,
    actor: str | None,
    params: dict[str, Any] | None = None,
    resolver: OwnerRefResolver | None = None,
) -> RunResult:
    """Feed one external event (an RPC) to the active arc.

    Returns ok=False with a reason for any legality rejection (no state changes): no
    active arc, wrong arc, unresolved owner, actor is not the owner, action not allowed
    here, or no matching transition passed its guard. On acceptance, runs the chosen
    transition and auto-advances, returning the resulting state.
    """

    event_params = dict(params or {})
    state = sink.current_state

    cursor = read_arc_cursor(state)
    if cursor is None:
        return RunResult(False, state, "no active arc")
    if cursor.arc_id != arc.id:
        return RunResult(
            False, state, f"active arc {cursor.arc_id!r} is not {arc.id!r}"
        )

    segment = arc.get(cursor.segment_id)
    if segment.is_automatic:
        raise RuntimeError(
            f"event {action_type!r} arrived at automatic segment "
            f"{arc.id}.{segment.id} (runner should have auto-advanced past it)"
        )

    owner_faction = resolve_owner(segment.owner, state, resolver)
    if owner_faction is None:
        return RunResult(
            False, state, f"segment {segment.id} has no resolved owner"
        )
    if actor != owner_faction:
        return RunResult(
            False,
            state,
            f"actor {actor!r} is not segment owner {owner_faction!r}",
        )
    if action_type not in segment.allowed_actions:
        return RunResult(
            False, state, f"action {action_type!r} not allowed in segment {segment.id}"
        )

    ctx = ArcContext(
        state=state,
        extension_key=state.title_bucket_key,
        owner_faction=owner_faction,
        params=event_params,
    )
    transition = _first_passing(segment.transitions, ctx, action_type=action_type)
    if transition is None:
        return RunResult(
            False,
            state,
            f"no {action_type!r} transition passed its guard in segment {segment.id}",
        )

    _apply_transition(
        sink, cursor, transition, owner_faction=owner_faction, params=event_params
    )
    final = _auto_advance(arc, sink, resolver)
    return RunResult(True, final)


__all__ = [
    "ActionSink",
    "OwnerRefResolver",
    "RunResult",
    "begin_arc",
    "resolve_owner",
    "submit_event",
]
