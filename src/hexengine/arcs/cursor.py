"""
Runtime arc cursor: the serialized position inside a declared arc.

The spec (see spec.py) is static code. The cursor is the small, mutable, snapshot-able
part: which segment of which arc is current, plus at most one suspended resume frame
(depth-1, per the plan). It lives in GameState.engine_state under a reserved engine key
and is changed only through the SetArcCursor StateAction, so undo/redo and snapshots
behave like every other engine mutation.

This step (0b) covers the cursor type, its JSON-safe (de)serialization, the engine-state
read/write helpers, and the StateAction. The generic runner (which decides when to
advance, suspend, resume, or finish) lands in a later step and simply composes pure
cursor transitions with SetArcCursor.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from ..state.action_manager import StateAction
from ..state.title_extension import engine_bucket, with_engine_bucket

if TYPE_CHECKING:
    from ..state.game_state import GameState

HEXENGINE_ARC_CURSOR_KEY = "hexengine_arc_cursor"

ARC_CURSOR_SCHEMA = 1


@dataclass(frozen=True, slots=True)
class SuspendedFrame:
    """A single suspended resume point within one arc.

    Recorded when an arc takes an Interrupt edge: it remembers the segment to return to
    once the interrupting sub-flow reaches a RESUME target. It stores only an in-arc
    segment id (no arc id) by design, so it can never resume into a different arc: arcs
    are distinct units and nothing carries across an arc boundary except the resulting
    GameState (see "Arc boundaries are clean" in the plan). Depth-1 means a cursor holds
    at most one of these at a time.
    """

    resume_segment_id: str


@dataclass(frozen=True, slots=True)
class ArcCursor:
    """The current position within one active arc, with an optional suspended frame."""

    arc_id: str
    segment_id: str
    suspended: SuspendedFrame | None = None

    @property
    def is_suspended(self) -> bool:
        """True when a resume frame is pending (the cursor is inside an interrupt)."""

        return self.suspended is not None

    def advanced_to(self, segment_id: str) -> ArcCursor:
        """Move to another segment in the same arc, keeping any suspended frame."""

        return replace(self, segment_id=str(segment_id))

    def suspended_into(self, segment_id: str, resume_segment_id: str) -> ArcCursor:
        """Take an interrupt: jump to segment_id and remember where to resume.

        Raises ValueError if a frame is already suspended (depth-1 invariant).
        """

        if self.suspended is not None:
            raise ValueError(
                "arc cursor already has a suspended frame (depth-1 only)"
            )
        return replace(
            self,
            segment_id=str(segment_id),
            suspended=SuspendedFrame(resume_segment_id=str(resume_segment_id)),
        )

    def resumed(self) -> ArcCursor:
        """Pop the suspended frame and continue at its resume segment.

        Raises ValueError if there is no frame to resume.
        """

        if self.suspended is None:
            raise ValueError("arc cursor has no suspended frame to resume")
        return replace(
            self, segment_id=self.suspended.resume_segment_id, suspended=None
        )


def cursor_to_snapshot(cursor: ArcCursor) -> dict[str, Any]:
    """JSON-safe dict for storing an ArcCursor in engine state."""

    snap: dict[str, Any] = {
        "schema": ARC_CURSOR_SCHEMA,
        "arc_id": str(cursor.arc_id),
        "segment_id": str(cursor.segment_id),
    }
    if cursor.suspended is not None:
        snap["suspended"] = {
            "resume_segment_id": str(cursor.suspended.resume_segment_id)
        }
    return snap


def cursor_from_snapshot(snap: Mapping[str, Any]) -> ArcCursor:
    """Inverse of cursor_to_snapshot (ignores the schema marker)."""

    raw_frame = snap.get("suspended")
    frame: SuspendedFrame | None = None
    if isinstance(raw_frame, Mapping):
        frame = SuspendedFrame(resume_segment_id=str(raw_frame["resume_segment_id"]))
    return ArcCursor(
        arc_id=str(snap["arc_id"]),
        segment_id=str(snap["segment_id"]),
        suspended=frame,
    )


def read_arc_cursor(state: GameState) -> ArcCursor | None:
    """Return the active arc cursor from engine state, or None when no arc is active."""

    raw = engine_bucket(state, HEXENGINE_ARC_CURSOR_KEY)
    if not raw:
        return None
    return cursor_from_snapshot(raw)


def with_arc_cursor(state: GameState, cursor: ArcCursor | None) -> GameState:
    """Return state with the active arc cursor set, or removed when cursor is None."""

    if cursor is None:
        es = dict(state.engine_state)
        es.pop(HEXENGINE_ARC_CURSOR_KEY, None)
        return state.with_engine_state(es)
    return with_engine_bucket(
        state, HEXENGINE_ARC_CURSOR_KEY, cursor_to_snapshot(cursor)
    )


class SetArcCursor(StateAction):
    """Replace the active arc cursor (undo restores the exact prior cursor entry).

    This is the single mutation point for the cursor. The generic runner computes the
    next cursor with the pure transitions on ArcCursor (advanced_to / suspended_into /
    resumed), or None to clear it on completion, and applies it through this action.
    """

    def __init__(self, cursor: ArcCursor | None) -> None:
        self.cursor = cursor
        self._prior_raw: dict[str, Any] | None = None

    def apply(self, state: GameState) -> GameState:
        prior = state.engine_state.get(HEXENGINE_ARC_CURSOR_KEY)
        self._prior_raw = dict(prior) if isinstance(prior, dict) else None
        return with_arc_cursor(state, self.cursor)

    def revert(self, state: GameState) -> GameState:
        es = dict(state.engine_state)
        if self._prior_raw is None:
            es.pop(HEXENGINE_ARC_CURSOR_KEY, None)
        else:
            es[HEXENGINE_ARC_CURSOR_KEY] = dict(self._prior_raw)
        return state.with_engine_state(es)

    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        if self.cursor is None:
            return "<SetArcCursor cleared>"
        return (
            f"<SetArcCursor {self.cursor.arc_id}.{self.cursor.segment_id}"
            f"{' suspended' if self.cursor.is_suspended else ''}>"
        )


__all__ = [
    "ARC_CURSOR_SCHEMA",
    "ArcCursor",
    "HEXENGINE_ARC_CURSOR_KEY",
    "SetArcCursor",
    "SuspendedFrame",
    "cursor_from_snapshot",
    "cursor_to_snapshot",
    "read_arc_cursor",
    "with_arc_cursor",
]
