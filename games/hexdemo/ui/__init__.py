"""Hexdemo client-facing UI helpers (segment registry, markup, focus)."""

from __future__ import annotations

from .focus import focus_unit_id_after_state_sync
from .marker_rules import default_marker_placement_rule
from .segment_registry import (
    PRESENTATION_BY_UI_MODE,
    Primitive,
    SegmentPresentation,
    resolve_presentation_id,
    segment_presentation,
)

__all__ = [
    "PRESENTATION_BY_UI_MODE",
    "Primitive",
    "SegmentPresentation",
    "default_marker_placement_rule",
    "focus_unit_id_after_state_sync",
    "resolve_presentation_id",
    "segment_presentation",
]
