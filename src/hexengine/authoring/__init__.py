"""
Author-time arc construction: builder, patterns, and validation.

Runtime engine code (server, runner, client) must not import this package except
through hexengine.hooks.internal.authoring_bridge (movement default) and
hexengine.hooks.internal.contracts (load-time validate).

Titles and tests import from here freely.
"""

from __future__ import annotations

from .builder import ArcBuilder, Case, Effect, Guard, SegmentBuilder, arc, case
from .patterns.phase import ROUTINE_SEGMENT, build_routine_phase_arc, simple_phase

__all__ = [
    "ArcBuilder",
    "Case",
    "Effect",
    "Guard",
    "ROUTINE_SEGMENT",
    "SegmentBuilder",
    "arc",
    "build_routine_phase_arc",
    "case",
    "simple_phase",
]
