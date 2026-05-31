"""Declarative, composable turn arcs (state machines over segments).

This package holds the canonical typed arc spec the engine drives generically. It is
separate from hexengine.server.arcs (the current imperative arc handlers) and from
hexengine.state.movement_arc (the movement arc wire keys); those are migrated onto this
model in later steps. See docs/COMPOSABLE_ARCS_PLAN.md.
"""

from __future__ import annotations

from .builder import (
    ArcBuilder,
    Case,
    Effect,
    Guard,
    SegmentBuilder,
    arc,
    case,
)
from .cursor import (
    ARC_CURSOR_SCHEMA,
    HEXENGINE_ARC_CURSOR_KEY,
    ArcCursor,
    SetArcCursor,
    SuspendedFrame,
    cursor_from_snapshot,
    cursor_to_snapshot,
    read_arc_cursor,
    with_arc_cursor,
)
from .spec import (
    AUTO,
    CURRENT,
    DONE,
    NO_OWNER,
    RESUME,
    Arc,
    ArcContext,
    AutoTrigger,
    Event,
    Faction,
    FlowEnd,
    Goto,
    Interrupt,
    Owner,
    OwnerRef,
    OwnerScope,
    Segment,
    Target,
    Transition,
    Trigger,
)

__all__ = [
    "ARC_CURSOR_SCHEMA",
    "AUTO",
    "Arc",
    "ArcBuilder",
    "ArcContext",
    "ArcCursor",
    "AutoTrigger",
    "CURRENT",
    "Case",
    "DONE",
    "Effect",
    "Event",
    "Faction",
    "FlowEnd",
    "Goto",
    "Guard",
    "HEXENGINE_ARC_CURSOR_KEY",
    "Interrupt",
    "NO_OWNER",
    "Owner",
    "OwnerRef",
    "OwnerScope",
    "RESUME",
    "Segment",
    "SegmentBuilder",
    "SetArcCursor",
    "SuspendedFrame",
    "Target",
    "Transition",
    "Trigger",
    "arc",
    "case",
    "cursor_from_snapshot",
    "cursor_to_snapshot",
    "read_arc_cursor",
    "with_arc_cursor",
]
