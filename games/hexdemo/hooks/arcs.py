"""
Hexdemo arc providers (composable arcs).

Combat uses unified ``combat_rules.BINDING`` via ``combat_rules_binding_to_arc_spec``.
"""

from __future__ import annotations

from hexengine.arcs.registry import TurnArcRegistry
from hexengine.hooks.arcs import ArcHook
from hexengine.hooks.wiring import bind_title_hook

from ..combat_arc import BINDING, build_hexdemo_combat_arc_spec
from ..turn_arc_schedule import build_hexdemo_turn_arc_registry

_COMBAT_ARC_SPEC = build_hexdemo_combat_arc_spec()
_TURN_ARC_REGISTRY = build_hexdemo_turn_arc_registry()


@bind_title_hook(ArcHook.COMBAT_ARC)
def combat_arc():
    return _COMBAT_ARC_SPEC


@bind_title_hook(ArcHook.COMBAT_RULES_BINDING)
def combat_rules_binding():
    return BINDING


@bind_title_hook(ArcHook.TURN_ARC_REGISTRY)
def turn_arc_registry() -> TurnArcRegistry:
    return _TURN_ARC_REGISTRY


__all__ = ["combat_arc", "combat_rules_binding", "turn_arc_registry"]
