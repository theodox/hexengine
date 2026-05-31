"""
Turn arc registry: schedule plus routine arc specs (composable arcs, Phase 4).

Titles expose a registry bundling the declared schedule and the routine phase arc specs
for each slot. Combat and movement arcs remain separate hook slots; lookup merges them.
"""

from __future__ import annotations

from dataclasses import dataclass

from .runner import ArcSpec
from .schedule import ArcSchedule


@dataclass(frozen=True, slots=True)
class TurnArcRegistry:
    """Title-owned turn schedule and routine arc specs keyed by `routine_arc_id`."""

    schedule: ArcSchedule
    routine_specs: dict[str, ArcSpec]


__all__ = ["TurnArcRegistry"]
