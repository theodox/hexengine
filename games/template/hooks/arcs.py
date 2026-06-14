"""
Declared turn arc registry (composable arcs).

Move-only titles omit ``ArcHook.MOVEMENT_ARC``. When enabling stepwise movement or
retreat-path continuation, bind ``ENGINE_MOVEMENT_ARC_PRESET`` (see hexdemo
``arcs/wiring.py``) or return a custom ``ArcSpec``.

When enabling combat: see ``combat_arc.build_template_combat_arc_spec``,
``segment_ui.py``, modification/interaction hooks, and TITLE_AUTHORING.md § Minimal combat title.
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
