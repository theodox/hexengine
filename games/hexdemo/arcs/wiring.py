"""``ArcHook`` adapters — turn registry and combat arc spec for ``TitleHooks.arcs``."""

from __future__ import annotations

from hexengine.hooks.core import ENGINE_MOVEMENT_ARC_PRESET
from hexengine.hooks.arcs import ArcHook
from hexengine.hooks.wiring import bind_title_hook

from ..combat.arc import BINDING, build_hexdemo_combat_arc_spec
from .turn_schedule import build_hexdemo_turn_arc_registry

_TURN_ARC_REGISTRY = build_hexdemo_turn_arc_registry()


@bind_title_hook(ArcHook.MOVEMENT_ARC)
def movement_arc():
    """Engine stepwise movement preset (retreat paths, optional resolve_move_as_steps)."""

    return ENGINE_MOVEMENT_ARC_PRESET


@bind_title_hook(ArcHook.COMBAT_ARC)
def combat_arc():
    return build_hexdemo_combat_arc_spec()


@bind_title_hook(ArcHook.COMBAT_RULES_BINDING)
def combat_rules_binding():
    return BINDING


@bind_title_hook(ArcHook.TURN_ARC_REGISTRY)
def turn_arc_registry():
    return _TURN_ARC_REGISTRY


__all__ = ["combat_arc", "combat_rules_binding", "movement_arc", "turn_arc_registry"]
