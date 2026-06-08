"""
Declarative arc state-machine spec (the canonical typed data contract).

An arc is a finite state machine that occupies part of a turn. This module defines the
static, inspectable spec the engine drives generically: segments (the states),
transitions (the edges), owners (who may act), and triggers (what fires an edge).

Effects and guards are plain Python callables; the spec itself is code, not JSON. Only
the runtime arc cursor (defined separately) is serialized into engine state. See
docs/COMPOSABLE_ARCS_PLAN.md for the model: the segment triple (owner / allowed_actions
/ resolution locus), the two structural operators (sequence, interrupt), and the
transition trigger/guard rules.

This step (0a) defines types and validation only; the generic runner, cursor, and
builder land in later steps.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..state.action_manager import StateAction
    from ..state.game_state import GameState


# ---- Owner ----------------------------------------------------------------


class OwnerScope(StrEnum):
    """Engine-generic owners resolved against turn state."""

    CURRENT = "current"
    """The scheduled current faction (TurnState.current_faction)."""

    NO_OWNER = "no_owner"
    """Ownerless: an automatic segment the engine advances without an external event."""


@dataclass(frozen=True, slots=True)
class Faction:
    """An explicit, fixed faction owner."""

    name: str


@dataclass(frozen=True, slots=True)
class OwnerRef:
    """A title-resolved owner, resolved by a title callable against an ArcContext.

    The engine does not interpret key. A title supplies the resolver (for example
    mapping "retreating" or "attacker" to a concrete faction for the current arc), so
    title-semantic owners need no engine knowledge.
    """

    key: str


Owner = OwnerScope | Faction | OwnerRef

CURRENT = OwnerScope.CURRENT
NO_OWNER = OwnerScope.NO_OWNER


# ---- Trigger --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Event:
    """External trigger: the segment owner submits this action type (an RPC)."""

    action_type: str


class AutoTrigger(Enum):
    """Singleton for automatic (engine-fired) transitions on ownerless segments."""

    AUTO = "auto"


AUTO = AutoTrigger.AUTO

Trigger = Event | AutoTrigger


# ---- Target ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Goto:
    """Advance to another segment in the same arc."""

    segment: str


@dataclass(frozen=True, slots=True)
class Interrupt:
    """Suspend to an in-arc sub-flow at segment, then resume at resume when it ends.

    Both segment and resume name segments of the same arc: interrupt never crosses an
    arc boundary (arcs are distinct units; see "Arc boundaries are clean" in the plan).
    Depth-1 by design: at most one suspended frame at a time.
    """

    segment: str
    resume: str


class FlowEnd(StrEnum):
    """Terminal targets that leave the current segment's arc."""

    DONE = "done"
    """The arc is complete."""

    RESUME = "resume"
    """Resume the suspended parent frame (used inside an interrupt sub-flow)."""


Target = Goto | Interrupt | FlowEnd

DONE = FlowEnd.DONE
RESUME = FlowEnd.RESUME


# ---- Context, transition, segment, arc ------------------------------------


@dataclass(frozen=True, slots=True)
class ArcContext:
    """Inputs passed to a transition guard or effect.

    owner_faction is the resolved acting faction (None for ownerless segments).
    params carries the triggering RPC payload (empty for automatic transitions).
    """

    state: GameState
    session_state_key: str | None
    owner_faction: str | None
    params: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Transition:
    """One edge: a trigger (with an optional guard), an optional effect, and a target.

    The guard is a pure predicate over the ArcContext. The effect returns the
    undoable StateActions to run when the edge is taken (RNG-bearing effects must
    draw from GameState.rng_log so replay and undo stay deterministic).
    """

    trigger: Trigger
    target: Target
    guard: Callable[[ArcContext], bool] | None = None
    effect: Callable[[ArcContext], list[StateAction]] | None = None


@dataclass(frozen=True, slots=True)
class Segment:
    """One state of an arc: an owner, an optional title label, and outgoing edges."""

    id: str
    owner: Owner
    transitions: tuple[Transition, ...]
    ui_mode: str = ""
    explicit_allowed_actions: frozenset[str] | None = None
    """When set, overrides Event-derived allowed_actions (routine phase segments)."""

    @property
    def is_automatic(self) -> bool:
        """True for ownerless segments the engine advances without an external event."""

        return self.owner is OwnerScope.NO_OWNER

    @property
    def allowed_actions(self) -> frozenset[str]:
        """Action types legal here (explicit list or derived from Event triggers)."""

        if self.explicit_allowed_actions is not None:
            return self.explicit_allowed_actions
        return frozenset(
            t.trigger.action_type
            for t in self.transitions
            if isinstance(t.trigger, Event)
        )


@dataclass(frozen=True, slots=True)
class Arc:
    """A named state machine: an entry segment id and its segments."""

    id: str
    entry: str
    segments: tuple[Segment, ...]

    def by_id(self) -> dict[str, Segment]:
        """Segments keyed by id (built on demand; the tuple is the source of truth)."""

        return {s.id: s for s in self.segments}

    def get(self, segment_id: str) -> Segment:
        """Return the segment with this id, or raise KeyError."""

        for s in self.segments:
            if s.id == segment_id:
                return s
        raise KeyError(f"Arc {self.id!r} has no segment {segment_id!r}")

    def validate(self) -> None:
        """Raise ValueError on a malformed arc.

        This is the seed of the load-time validation called for in the plan: there are
        no silent runtime fallbacks, so a bad arc must fail loudly and early. Checks
        cover empty/duplicate segment ids, a real entry, that each segment has at least
        one transition, that trigger kind matches the owner (ownerless segments use
        AUTO, owned segments use Event), and that every goto/interrupt/resume target
        names a real segment.
        """

        if not self.segments:
            raise ValueError(f"Arc {self.id!r} has no segments")

        ids = [s.id for s in self.segments]
        duplicates = sorted({x for x in ids if ids.count(x) > 1})
        if duplicates:
            raise ValueError(f"Arc {self.id!r} has duplicate segment ids: {duplicates}")

        known = set(ids)
        if self.entry not in known:
            raise ValueError(
                f"Arc {self.id!r} entry {self.entry!r} is not one of its segments"
            )

        for s in self.segments:
            if not s.transitions:
                if s.explicit_allowed_actions is None:
                    raise ValueError(f"Segment {self.id}.{s.id} has no transitions")
                continue
            for t in s.transitions:
                if s.is_automatic:
                    if not isinstance(t.trigger, AutoTrigger):
                        raise ValueError(
                            f"Ownerless segment {self.id}.{s.id} must use AUTO "
                            f"triggers, got {t.trigger!r}"
                        )
                else:
                    if not isinstance(t.trigger, Event):
                        raise ValueError(
                            f"Owned segment {self.id}.{s.id} must use Event triggers, "
                            f"got {t.trigger!r}"
                        )
                self._validate_target(s.id, t.target, known)

    def _validate_target(
        self, segment_id: str, target: Target, known: set[str]
    ) -> None:
        if isinstance(target, Goto):
            if target.segment not in known:
                raise ValueError(
                    f"{self.id}.{segment_id} goto {target.segment!r} is not a segment"
                )
        elif isinstance(target, Interrupt):
            if target.segment not in known:
                raise ValueError(
                    f"{self.id}.{segment_id} interrupt {target.segment!r} is not a "
                    f"segment"
                )
            if target.resume not in known:
                raise ValueError(
                    f"{self.id}.{segment_id} interrupt resume {target.resume!r} is "
                    f"not a segment"
                )


__all__ = [
    "AUTO",
    "Arc",
    "ArcContext",
    "AutoTrigger",
    "CURRENT",
    "DONE",
    "Event",
    "Faction",
    "FlowEnd",
    "Goto",
    "Interrupt",
    "NO_OWNER",
    "Owner",
    "OwnerRef",
    "OwnerScope",
    "RESUME",
    "Segment",
    "Target",
    "Transition",
    "Trigger",
]
