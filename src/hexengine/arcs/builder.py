"""
Context-manager builder for declaring arcs.

This is the default authoring surface. It is thin and side-effect-free: it only
assembles and returns the canonical typed spec from spec.py (Arc / Segment /
Transition), which stays the real contract the engine consumes. The builder adds
ergonomics, not semantics:

- you never type allowed_actions; it is derived from each segment's Event triggers,
- targets read as keywords (goto / done / resume / interrupt+resume_at) instead of
  constructing Goto / FlowEnd / Interrupt by hand,
- branch / case express guarded fan-out (the same trigger choosing among targets by
  guard) without repeating the trigger.

There is deliberately no operator overloading or decorator magic on this path, so the
output stays statically typed and inspectable. A "prettiness" operator layer, if ever
added, is strictly optional and must emit this same data (see the plan, Phase 6).

Example:

    with arc("combat") as a:  # entry defaults to the first segment
        with a.segment("attack", owner=CURRENT, kind="routine") as s:
            s.on("Attack", interrupt="retreat_gate", resume_at="advance_gate",
                 effect=apply_attack)
        with a.segment("retreat_gate", owner=OwnerRef("retreating"),
                       kind="retreat_gate") as s:
            s.on("RetreatUnit", resume=True, effect=do_retreat)
            s.on("DisruptInsteadOfRetreat", resume=True, effect=do_disrupt)
        with a.segment("advance_gate", owner=CURRENT, kind="advance_gate") as s:
            s.on("CombatAdvance", done=True, effect=do_advance)
            s.on("DeclineAdvance", done=True)
    combat = a.build()
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import TYPE_CHECKING

from .spec import (
    AUTO,
    Arc,
    ArcContext,
    Event,
    FlowEnd,
    Goto,
    Interrupt,
    Owner,
    Segment,
    Target,
    Transition,
)

if TYPE_CHECKING:
    from ..state.action_manager import StateAction

Guard = Callable[[ArcContext], bool]
Effect = Callable[[ArcContext], "list[StateAction]"]


def _resolve_target(
    *,
    goto: str | None,
    done: bool,
    resume: bool,
    interrupt: str | None,
    resume_at: str | None,
) -> Target:
    """Turn the keyword target options into exactly one canonical Target."""

    chosen = [
        name
        for name, picked in (
            ("goto", goto is not None),
            ("done", done),
            ("resume", resume),
            ("interrupt", interrupt is not None),
        )
        if picked
    ]
    if len(chosen) != 1:
        raise ValueError(
            "a transition needs exactly one target "
            f"(goto / done / resume / interrupt), got {chosen or 'none'}"
        )

    if interrupt is not None:
        if not resume_at:
            raise ValueError(
                "interrupt requires resume_at (the in-arc segment to resume at)"
            )
        return Interrupt(segment=str(interrupt), resume=str(resume_at))
    if resume_at:
        raise ValueError("resume_at is only valid together with interrupt")
    if goto is not None:
        return Goto(segment=str(goto))
    if done:
        return FlowEnd.DONE
    return FlowEnd.RESUME


@dataclass(frozen=True, slots=True)
class Case:
    """One guarded branch arm: a resolved target plus an optional guard and effect."""

    target: Target
    guard: Guard | None = None
    effect: Effect | None = None


def case(
    *,
    goto: str | None = None,
    done: bool = False,
    resume: bool = False,
    interrupt: str | None = None,
    resume_at: str | None = None,
    guard: Guard | None = None,
    effect: Effect | None = None,
) -> Case:
    """Build one arm for branch/auto_branch (a target chosen when guard passes).

    Arms are evaluated in order; the last arm typically has no guard (the default).
    """

    return Case(
        target=_resolve_target(
            goto=goto, done=done, resume=resume, interrupt=interrupt, resume_at=resume_at
        ),
        guard=guard,
        effect=effect,
    )


class SegmentBuilder:
    """Collects the transitions of one segment; commits the Segment on block exit."""

    def __init__(self, arc_builder: ArcBuilder, segment_id: str, owner: Owner, kind: str):
        self._arc = arc_builder
        self._id = str(segment_id)
        self._owner = owner
        self._kind = str(kind)
        self._transitions: list[Transition] = []

    def __enter__(self) -> SegmentBuilder:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        if exc_type is None:
            self._arc._add_segment(
                Segment(
                    id=self._id,
                    owner=self._owner,
                    transitions=tuple(self._transitions),
                    kind=self._kind,
                )
            )
        return False

    def on(
        self,
        action_type: str,
        *,
        goto: str | None = None,
        done: bool = False,
        resume: bool = False,
        interrupt: str | None = None,
        resume_at: str | None = None,
        guard: Guard | None = None,
        effect: Effect | None = None,
    ) -> SegmentBuilder:
        """Add an external (Event-triggered) transition. Returns self for chaining."""

        self._transitions.append(
            Transition(
                trigger=Event(str(action_type)),
                target=_resolve_target(
                    goto=goto,
                    done=done,
                    resume=resume,
                    interrupt=interrupt,
                    resume_at=resume_at,
                ),
                guard=guard,
                effect=effect,
            )
        )
        return self

    def auto(
        self,
        *,
        goto: str | None = None,
        done: bool = False,
        resume: bool = False,
        interrupt: str | None = None,
        resume_at: str | None = None,
        guard: Guard | None = None,
        effect: Effect | None = None,
    ) -> SegmentBuilder:
        """Add an automatic (engine-fired) transition for an ownerless segment."""

        self._transitions.append(
            Transition(
                trigger=AUTO,
                target=_resolve_target(
                    goto=goto,
                    done=done,
                    resume=resume,
                    interrupt=interrupt,
                    resume_at=resume_at,
                ),
                guard=guard,
                effect=effect,
            )
        )
        return self

    def branch(self, action_type: str, *cases: Case) -> SegmentBuilder:
        """Add several Event transitions for one trigger, choosing a target by guard."""

        for c in cases:
            self._transitions.append(
                Transition(
                    trigger=Event(str(action_type)),
                    target=c.target,
                    guard=c.guard,
                    effect=c.effect,
                )
            )
        return self

    def auto_branch(self, *cases: Case) -> SegmentBuilder:
        """Add several automatic transitions, choosing a target by guard (in order)."""

        for c in cases:
            self._transitions.append(
                Transition(
                    trigger=AUTO, target=c.target, guard=c.guard, effect=c.effect
                )
            )
        return self


class ArcBuilder:
    """Accumulates segments and produces a validated Arc on build()."""

    def __init__(self, arc_id: str, entry: str | None = None):
        self._id = str(arc_id)
        self._entry = entry
        self._segments: list[Segment] = []

    def __enter__(self) -> ArcBuilder:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False

    def segment(self, segment_id: str, *, owner: Owner, kind: str = "") -> SegmentBuilder:
        """Open a segment block; its transitions are committed when the block exits."""

        return SegmentBuilder(self, segment_id, owner, kind)

    def _add_segment(self, seg: Segment) -> None:
        self._segments.append(seg)

    def build(self, *, validate: bool = True) -> Arc:
        """Return the assembled Arc. Entry defaults to the first segment declared.

        Validates by default (Arc.validate); pass validate=False only when building a
        partial arc on purpose (e.g. composing fragments in a test).
        """

        if self._entry is not None:
            entry = self._entry
        elif self._segments:
            entry = self._segments[0].id
        else:
            raise ValueError(f"arc {self._id!r} has no segments and no entry")
        arc_obj = Arc(id=self._id, entry=entry, segments=tuple(self._segments))
        if validate:
            arc_obj.validate()
        return arc_obj


def arc(arc_id: str, entry: str | None = None) -> ArcBuilder:
    """Open an arc builder. Use as a context manager; call build() after the block."""

    return ArcBuilder(arc_id, entry)


__all__ = [
    "ArcBuilder",
    "Case",
    "Effect",
    "Guard",
    "SegmentBuilder",
    "arc",
    "case",
]
