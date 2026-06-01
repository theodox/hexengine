"""
Declared turn arc registry (composable arcs).

Combat and movement overlay arcs: add ArcHook bindings here when the title needs them.
"""

from __future__ import annotations

from hexengine.arcs.registry import TurnArcRegistry
from hexengine.hooks.arcs import ArcHook
from hexengine.hooks.wiring import bind_title_hook

from ..turn_arc_schedule import build_template_turn_arc_registry

_TURN_ARC_REGISTRY = build_template_turn_arc_registry()


@bind_title_hook(ArcHook.TURN_ARC_REGISTRY)
def turn_arc_registry() -> TurnArcRegistry:
    return _TURN_ARC_REGISTRY


__all__ = ["turn_arc_registry"]
