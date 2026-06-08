"""Hexdemo declared arc helpers (segment projection and turn schedule)."""

from __future__ import annotations

from . import segment
from .segment import (
    phase_advance_blocked,
    project_segment_for_faction,
    segment_allows,
    segment_denies_action,
    segment_ui_mode,
)
from .turn_schedule import build_hexdemo_turn_arc_registry, hexdemo_schedule_slots

__all__ = [
    "segment",
    "phase_advance_blocked",
    "project_segment_for_faction",
    "segment_allows",
    "segment_denies_action",
    "segment_ui_mode",
    "build_hexdemo_turn_arc_registry",
    "hexdemo_schedule_slots",
]
