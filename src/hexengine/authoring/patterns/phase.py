"""
Routine phase arc pattern: one owned segment per schedule slot.
"""

from __future__ import annotations

from ...arcs.spec import CURRENT, Arc
from ..builder import arc

ROUTINE_SEGMENT = "routine"


def simple_phase(
    arc_id: str,
    *,
    allowed_actions: frozenset[str],
    ui_mode: str = "routine",
) -> Arc:
    """Build a single-segment routine arc for one schedule slot."""

    with arc(str(arc_id), entry=ROUTINE_SEGMENT) as a:
        with a.segment(
            ROUTINE_SEGMENT,
            owner=CURRENT,
            ui_mode=str(ui_mode),
            allowed_actions=allowed_actions,
        ):
            pass

    return a.build()


build_routine_phase_arc = simple_phase

__all__ = ["ROUTINE_SEGMENT", "build_routine_phase_arc", "simple_phase"]
