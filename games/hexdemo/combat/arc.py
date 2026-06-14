"""Hexdemo combat ``ArcSpec`` — owner resolver and hook-facing spec builder."""

from __future__ import annotations

from hexengine.arcs import Arc
from hexengine.authoring.patterns.combat import (
    OWNER_RETREATING,
    combat_arc_to_spec,
    combat_rules_binding_missing_methods,
    combat_rules_binding_satisfies,
    combat_rules_effects_adapter,
)
from hexengine.state import GameState

from ..state import session_state
from . import rules, transitions
from .graph import (
    SEG_ADVANCE_GATE,
    SEG_ATTACK,
    SEG_CLASSIFY,
    SEG_RESOLVE,
    SEG_RETREAT_GATE,
    SEG_RETREAT_OR_DISRUPT_GATE,
    build_hexdemo_combat_arc,
)

BINDING = rules.BINDING

_COMBAT_ARC_SPEC = None


def retreating_faction(state: GameState) -> str | None:
    if not state.session_state_key:
        return None
    ro = session_state.retreat_obligations(state)
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
        if not combat_rules_binding_satisfies(BINDING):
            missing = ", ".join(combat_rules_binding_missing_methods(BINDING))
            raise TypeError(f"CombatRulesBinding missing methods: {missing}")
        effects = combat_rules_effects_adapter(BINDING)
        arc = build_hexdemo_combat_arc(
            effects,
            transitions.COMBAT_ARC_GATE_UI_MODES,
            attack_effect=BINDING.attack_arc_effect,
        )
        _COMBAT_ARC_SPEC = combat_arc_to_spec(
            arc,
            owner_resolver=resolve_owner_ref,
            advance_move_detector=BINDING.detect_combat_advance_move,
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
