"""Declarative, composable turn arcs (state machines over segments).

This package holds the canonical typed arc spec the engine drives generically. It is
separate from hexengine.server.arcs (the current imperative arc handlers) and from
hexengine.state.movement_arc (the movement arc wire keys); those are migrated onto this
model in later steps. See docs/COMPOSABLE_ARCS_PLAN.md.
"""

from __future__ import annotations

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
