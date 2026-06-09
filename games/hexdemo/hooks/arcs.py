"""Wire ``ArcHook`` slots to hexdemo arc providers."""

from __future__ import annotations

from ..arcs.turn_schedule import build_hexdemo_turn_arc_registry
from ..combat.arc import BINDING, build_hexdemo_combat_arc_spec

_TURN_ARC_REGISTRY = build_hexdemo_turn_arc_registry()

ARCS_HOOKS = {
    "combat_arc": build_hexdemo_combat_arc_spec,
    "combat_rules_binding": lambda: BINDING,
    "turn_arc_registry": lambda: _TURN_ARC_REGISTRY,
}

__all__ = ["ARCS_HOOKS"]
