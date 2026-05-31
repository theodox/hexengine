"""
Routine phase arc: one owned segment for a schedule slot (composable arcs, Phase 4).

A routine arc holds the schedule slot's allowed RPC types until `NextPhase` clears the
cursor and the schedule advances. Transitions are empty; legality reads
`segment.allowed_actions` and `segment.owner` without routing every RPC through the runner.
"""

from __future__ import annotations

from . import CURRENT, Arc, arc
from .spec import Arc as ArcType

ROUTINE_SEGMENT = "routine"


def build_routine_phase_arc(
    arc_id: str,
    *,
    allowed_actions: frozenset[str],
    kind: str = "routine",
) -> ArcType:
    """Build a single-segment routine arc for one schedule slot."""

    with arc(str(arc_id), entry=ROUTINE_SEGMENT) as a:
        with a.segment(
            ROUTINE_SEGMENT,
            owner=CURRENT,
            kind=str(kind),
            allowed_actions=allowed_actions,
        ):
            pass

    return a.build()


__all__ = ["ROUTINE_SEGMENT", "build_routine_phase_arc"]
