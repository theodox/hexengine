"""Hexdemo combat policy, arc spec, and cleanup actions."""

from __future__ import annotations

from . import actions, arc, outcome, planning, rules, transitions
from .arc import (
    BINDING,
    SEG_ADVANCE_GATE,
    SEG_ATTACK,
    SEG_CLASSIFY,
    SEG_RESOLVE,
    SEG_RETREAT_GATE,
    SEG_RETREAT_OR_DISRUPT_GATE,
    build_combat_arc,
    build_hexdemo_combat_arc_spec,
)
from .rules import (
    HexdemoCombatRules,
    check_morale,
    combat_outcome_after_applied,
    get_combat_factor,
    resolve_attack,
    validate_attack,
)
from .transitions import (
    COMBAT_ARC_GATE_UI_MODES,
    GATE_AWAITING_ADVANCE,
    GATE_AWAITING_RETREAT,
    GATE_AWAITING_RETREAT_OR_DISRUPT,
    attack_planning_blocked_reason,
    clear_combat_state_actions,
)

__all__ = [
    "BINDING",
    "COMBAT_ARC_GATE_UI_MODES",
    "GATE_AWAITING_ADVANCE",
    "GATE_AWAITING_RETREAT",
    "GATE_AWAITING_RETREAT_OR_DISRUPT",
    "HexdemoCombatRules",
    "SEG_ADVANCE_GATE",
    "SEG_ATTACK",
    "SEG_CLASSIFY",
    "SEG_RESOLVE",
    "SEG_RETREAT_GATE",
    "SEG_RETREAT_OR_DISRUPT_GATE",
    "actions",
    "arc",
    "attack_planning_blocked_reason",
    "build_combat_arc",
    "build_hexdemo_combat_arc_spec",
    "check_morale",
    "clear_combat_state_actions",
    "combat_outcome_after_applied",
    "get_combat_factor",
    "outcome",
    "planning",
    "resolve_attack",
    "rules",
    "transitions",
    "validate_attack",
]
