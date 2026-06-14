"""
Stepwise movement arc pattern (host-bound effects injected at assembly time).

Borrow-only: re-exports the engine graph builder from ``hexengine.arcs.movement_arc_build``.
"""

from __future__ import annotations

from ...arcs.movement_arc_build import build_movement_arc

__all__ = ["build_movement_arc"]
