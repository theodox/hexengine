"""
Hexdemo combat arc — built from ``combat_rules.BINDING``.
"""

from __future__ import annotations

from hexengine.arcs import Arc
from hexengine.authoring.patterns.combat import (
    COMBAT_ARC_ID,
    OWNER_RETREATING,
    SEG_ADVANCE_GATE,
    SEG_ATTACK,
    SEG_CLASSIFY,
    SEG_RESOLVE,
    SEG_RETREAT_GATE,
    SEG_RETREAT_OR_DISRUPT_GATE,
    combat_rules_binding_to_arc_spec,
)
from hexengine.state import GameState
from . import combat_rules, combat_transitions, title_state

BINDING = combat_rules.BINDING

_COMBAT_ARC_SPEC = None


def retreating_faction(state: GameState) -> str | None:
    if not state.title_bucket_key:
        return None
    ro = title_state.retreat_obligations(state)
    for uid, raw in ro.items():
        try:
            if int(raw) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        u = state.board.units.get(str(uid))
        if u is not None and u.active:
            return str(u.faction)
    return None


def resolve_owner_ref(key: str, state: GameState) -> str | None:
    if key == OWNER_RETREATING:
        return retreating_faction(state)
    return None


def build_hexdemo_combat_arc_spec():
    global _COMBAT_ARC_SPEC
    if _COMBAT_ARC_SPEC is None:
        _COMBAT_ARC_SPEC = combat_rules_binding_to_arc_spec(
            BINDING,
            combat_transitions.COMBAT_ARC_GATE_KINDS,
            arc_id=COMBAT_ARC_ID,
            owner_resolver=resolve_owner_ref,
            attack_effect=BINDING.attack_arc_effect,
        )
    return _COMBAT_ARC_SPEC


def build_combat_arc() -> Arc:
    """Build the hexdemo combat arc graph (parity tests and declarations)."""

    return build_hexdemo_combat_arc_spec().arc


__all__ = [
    "BINDING",
    "OWNER_RETREATING",
    "SEG_ADVANCE_GATE",
    "SEG_ATTACK",
    "SEG_CLASSIFY",
    "SEG_RESOLVE",
    "SEG_RETREAT_GATE",
    "SEG_RETREAT_OR_DISRUPT_GATE",
    "build_combat_arc",
    "build_hexdemo_combat_arc_spec",
    "resolve_owner_ref",
    "retreating_faction",
]
