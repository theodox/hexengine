"""
Discover interaction capabilities from a declared arc graph (charter E).

Authority modules scan segment Event triggers — not engine-global segment ids such as
``attack`` or arc ids such as ``combat``.
"""

from __future__ import annotations

from .spec import Arc, Event


def arc_event_segments(arc: Arc, action_type: str) -> tuple[str, ...]:
    """Segment ids that declare an ``Event(action_type)`` transition (declaration order)."""

    action = str(action_type).strip()
    if not action:
        return ()
    out: list[str] = []
    for seg in arc.segments:
        for transition in seg.transitions:
            trigger = transition.trigger
            if isinstance(trigger, Event) and trigger.action_type == action:
                out.append(seg.id)
                break
    return tuple(out)


def arc_supports_action_type(arc: Arc, action_type: str) -> bool:
    """True when the arc graph handles ``action_type`` via at least one Event transition."""

    return bool(arc_event_segments(arc, action_type))


def arc_commit_segment_for_action(arc: Arc, action_type: str) -> str:
    """
    Segment id to use as the arc cursor before ``submit_event`` for ``action_type``.

    Picks the first segment (in arc declaration order) whose transitions include
    ``Event(action_type)``. When multiple segments accept the same action, the earliest
    declared segment wins — titles should declare at most one commit segment per action.
    """

    segments = arc_event_segments(arc, action_type)
    if not segments:
        raise ValueError(
            f"Arc {arc.id!r} has no segment with Event({action_type!r}) transition"
        )
    return segments[0]


__all__ = [
    "arc_commit_segment_for_action",
    "arc_event_segments",
    "arc_supports_action_type",
]
