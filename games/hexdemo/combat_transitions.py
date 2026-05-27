"""
Hexdemo combat gate FSM (title-owned; the engine does not enumerate these values).

State table (``combat_gate`` in the title bucket):

| Gate | End phase / auto-advance | Attack planning | Typical entry |
|------|--------------------------|-----------------|---------------|
| (none) | allowed when no retreat obligations | allowed | routine combat segment |
| ``awaiting_retreat`` | blocked | blocked | ``Attack`` retreat outcome |
| ``awaiting_retreat_or_disrupt`` | blocked | blocked | CRT optional disrupt follow-up |
| ``awaiting_advance`` | blocked | blocked | post-retreat advance window |

Transitions:

- routine + retreat outcome → ``awaiting_retreat`` (engine ``Attack``)
- ``awaiting_retreat`` + optional disrupt → ``awaiting_retreat_or_disrupt`` (``follow_up_after_attack``)
- obligations cleared + policy → ``awaiting_advance`` (``on_retreat_obligation_cleared`` / ``OpenCombatAdvance``)
- advance move or skip → (none)
"""

from __future__ import annotations

from typing import Any

from hexengine.hooks.attack import (
    AfterAttackAppliedContext,
    RetreatObligationClearedContext,
)
from hexengine.hooks.internal.advance import default_maybe_open_combat_advance_after_retreat
from hexengine.state import GameState
from hexengine.state.action_manager import StateAction
from hexengine.state.actions import OpenCombatAdvance, PatchTitleBucket

from . import combat, title_state

# Wire values stored in ``extension[pack_id]["combat_gate"]``.
GATE_AWAITING_RETREAT = "awaiting_retreat"
GATE_AWAITING_RETREAT_OR_DISRUPT = "awaiting_retreat_or_disrupt"
GATE_AWAITING_ADVANCE = "awaiting_advance"

# Short aliases for docs and call sites.
GATE_RETREAT = GATE_AWAITING_RETREAT
GATE_ADVANCE = GATE_AWAITING_ADVANCE

GATES_BLOCKING_ROUTINE: frozenset[str] = frozenset(
    {
        GATE_AWAITING_RETREAT,
        GATE_AWAITING_RETREAT_OR_DISRUPT,
        GATE_AWAITING_ADVANCE,
    }
)

# Turn-action dock ``dock_arc`` tokens (UI only, not stored in extension).
DOCK_ARC_HIDDEN = "hidden"
DOCK_ARC_RETREAT_GATE = "retreat_gate"
DOCK_ARC_ADVANCE_GATE = "advance_gate"
DOCK_ARC_ATTACK_READY = "attack_ready"
DOCK_ARC_ROUTINE = "routine"


def current_combat_gate(state: GameState) -> str:
    """Normalized ``combat_gate`` string from the hexdemo bucket (``""`` if unset)."""

    return str(title_state.bucket(state).get("combat_gate", "")).strip()


def blocks_routine_phase_advance(state: GameState) -> bool:
    """True when retreat obligations or a combat gate forbid End Phase / auto-advance."""

    if combat.any_retreat_obligation_pending(state):
        return True
    return current_combat_gate(state) in GATES_BLOCKING_ROUTINE


def attack_planning_blocked_reason(
    state: GameState, player_faction: str
) -> str | None:
    """Human-readable block reason for attack plan preview, or ``None`` if allowed."""

    if str(player_faction).strip() != str(state.turn.current_faction).strip():
        return "Not your turn"
    phase = str(state.turn.current_phase).strip()
    if phase not in ("Combat", "Attack"):
        return "Attack planning is only available during Combat"
    if combat.any_retreat_obligation_pending(state):
        return "Resolve retreat before planning an attack"
    gate = current_combat_gate(state)
    if gate == GATE_AWAITING_ADVANCE:
        return "Resolve combat advance before planning an attack"
    if gate == GATE_AWAITING_RETREAT_OR_DISRUPT:
        return "Resolve retreat before planning an attack"
    if gate == GATE_AWAITING_RETREAT:
        return "Resolve retreat before planning an attack"
    return None


def dock_arc_hint(
    *,
    state: GameState,
    viewer_faction: str | None,
    viewer_is_turn_owner: bool,
    current_phase: str,
    gate_actions: list[dict[str, Any]],
) -> str:
    """
    Turn-action dock arc for the viewer (retreat gate, advance gate, attack-ready, routine).
    """

    for row in gate_actions:
        if not isinstance(row, dict):
            continue
        at = str(row.get("action_type", "")).strip()
        if at == "CombatDisruptInsteadOfRetreat":
            return DOCK_ARC_RETREAT_GATE
        if at == "CombatAdvance":
            return DOCK_ARC_ADVANCE_GATE
    my = str(viewer_faction or "").strip()
    if my and combat.faction_has_pending_retreat(state, my):
        return DOCK_ARC_RETREAT_GATE
    if not viewer_is_turn_owner:
        return DOCK_ARC_HIDDEN
    if str(current_phase).strip() == "Combat":
        return DOCK_ARC_ATTACK_READY
    return DOCK_ARC_ROUTINE


def follow_up_after_attack(ctx: AfterAttackAppliedContext) -> list[StateAction]:
    """Title-owned follow-ups after ``Attack`` and ``ApplyCombatEffects``."""

    actions: list[StateAction] = []
    eff = ctx.resolution.effects
    if isinstance(eff, dict):
        retreat_meta = eff.get("retreat")
        if (
            isinstance(retreat_meta, dict)
            and retreat_meta.get("allow_disrupt_instead")
            and current_combat_gate(ctx.state) == GATE_AWAITING_RETREAT
        ):
            actions.append(
                PatchTitleBucket(
                    ctx.extension_key,
                    {"combat_gate": GATE_AWAITING_RETREAT_OR_DISRUPT},
                )
            )
    return actions


def on_retreat_obligation_cleared(
    ctx: RetreatObligationClearedContext,
) -> OpenCombatAdvance | None:
    """Open optional post-retreat advance when engine default rules match."""

    return default_maybe_open_combat_advance_after_retreat(ctx.state, ctx.extension_key)


__all__ = [
    "DOCK_ARC_ADVANCE_GATE",
    "DOCK_ARC_ATTACK_READY",
    "DOCK_ARC_HIDDEN",
    "DOCK_ARC_RETREAT_GATE",
    "DOCK_ARC_ROUTINE",
    "GATE_ADVANCE",
    "GATE_AWAITING_ADVANCE",
    "GATE_AWAITING_RETREAT",
    "GATE_AWAITING_RETREAT_OR_DISRUPT",
    "GATE_RETREAT",
    "GATES_BLOCKING_ROUTINE",
    "attack_planning_blocked_reason",
    "blocks_routine_phase_advance",
    "current_combat_gate",
    "dock_arc_hint",
    "follow_up_after_attack",
    "on_retreat_obligation_cleared",
]
