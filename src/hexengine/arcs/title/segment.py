"""Active-segment projection helpers for title pack code."""

from __future__ import annotations

from ..segment_wire import (
    project_current_segment,
    segment_allows_action,
    segment_blocks_routine_phase_advance,
    segment_denies_action_for_faction,
)

__all__ = [
    "project_current_segment",
    "segment_allows_action",
    "segment_blocks_routine_phase_advance",
    "segment_denies_action_for_faction",
]
