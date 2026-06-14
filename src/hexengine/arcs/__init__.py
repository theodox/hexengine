"""Declarative, composable turn arcs (state machines over segments).

Runtime contract: spec, cursor, runner, schedule types, segment wire projection.
Author-time construction lives in hexengine.authoring (builder + patterns).
"""

from __future__ import annotations

from .capabilities import (
    arc_commit_segment_for_action,
    arc_event_action_types,
    arc_event_segments,
    arc_supports_action_type,
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
from .registry import TurnArcRegistry
from .runner import (
    ActionSink,
    ArcSpec,
    OwnerRefResolver,
    RunResult,
    begin_arc,
    resolve_owner,
    submit_event,
)
from .schedule import ArcSchedule, ScheduleSlot
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
    "ActionSink",
    "Arc",
    "ArcContext",
    "ArcCursor",
    "ArcSchedule",
    "ArcSpec",
    "AutoTrigger",
    "CURRENT",
    "DONE",
    "Event",
    "Faction",
    "FlowEnd",
    "Goto",
    "HEXENGINE_ARC_CURSOR_KEY",
    "Interrupt",
    "NO_OWNER",
    "Owner",
    "OwnerRef",
    "OwnerRefResolver",
    "OwnerScope",
    "RESUME",
    "RunResult",
    "ScheduleSlot",
    "Segment",
    "SetArcCursor",
    "SuspendedFrame",
    "Target",
    "Transition",
    "Trigger",
    "TurnArcRegistry",
    "arc_commit_segment_for_action",
    "arc_event_action_types",
    "arc_event_segments",
    "arc_supports_action_type",
    "begin_arc",
    "cursor_from_snapshot",
    "cursor_to_snapshot",
    "read_arc_cursor",
    "resolve_owner",
    "submit_event",
    "with_arc_cursor",
]
