"""
Host-bound stepwise movement ``ArcSpec`` assembly (engine preset, not title patterns).
"""

from __future__ import annotations

from typing import Any, Protocol

from ...arcs import ArcSpec
from ...arcs.movement_arc_build import build_movement_arc
from ...arcs.movement_arc_decl import resolve_moving_faction
from .movement_arc_effects import MovementArcEffects


class MovementArcHost(Protocol):
    """Minimal server surface for host-bound movement arc effects."""

    hooks: Any


def build_host_bound_movement_arc_spec(host: MovementArcHost) -> ArcSpec:
    """Assemble the engine stepwise movement arc for an authoritative server host."""

    effects = MovementArcEffects(host)  # type: ignore[arg-type]
    return ArcSpec(
        arc=build_movement_arc(effects),
        owner_resolver=resolve_moving_faction,
    )


__all__ = ["MovementArcHost", "build_host_bound_movement_arc_spec"]
