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

- routine + retreat outcome → ``awaiting_retreat`` (``follow_up_after_attack``)
- ``awaiting_retreat`` + optional disrupt → ``awaiting_retreat_or_disrupt`` (``follow_up_after_attack``)
- obligations cleared + policy → ``awaiting_advance`` (``on_retreat_obligation_cleared`` / pack ``combat_actions``)
- advance move or skip → (none)
"""

from __future__ import annotations

from typing import Any

from hexengine.hooks.attack import (
    AfterAttackAppliedContext,
    RetreatObligationClearedContext,
)
from hexengine.state import GameState
from hexengine.state.action_manager import StateAction
from hexengine.state.actions import PatchTitleBucket

from . import combat, combat_actions, title_state

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

# Title bucket keys that are scoped to a single combat segment and cleared on phase
# advance. The engine does not know these names; hexdemo clears them in
# `after_phase_transition`.
PHASE_SCOPED_COMBAT_KEYS: tuple[str, ...] = (
    "attacks_this_phase",
    "retreat_obligations",
    "combat_gate",
    "last_combat",
    "advance",
)


def clear_combat_state_actions(state: GameState) -> list[StateAction]:
    """Actions to drop phase-scoped combat keys from the hexdemo bucket on phase advance."""

    ek = state.title_bucket_key
    if not ek:
        return []
    if not title_state.bucket(state):
        return []
    return [
        PatchTitleBucket(ek, {}, remove_keys=PHASE_SCOPED_COMBAT_KEYS),
    ]

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
    outcome = str(ctx.resolution.outcome or "").strip()
    a_ids = (
        tuple(ctx.resolution.attacker_ids)
        if ctx.resolution.attacker_ids
        else tuple(ctx.attack_context.attacker_ids)
    )
    d_ids = (
        tuple(ctx.resolution.defender_ids)
        if ctx.resolution.defender_ids
        else tuple(ctx.attack_context.defender_ids)
    )

    # Update "attacks_this_phase" (one entry per attacking unit).
    hx0 = title_state.bucket(ctx.state)
    prev_attacks = hx0.get("attacks_this_phase")
    attacks = list(prev_attacks) if isinstance(prev_attacks, list) else []
    for aid in a_ids:
        if isinstance(aid, str) and aid.strip():
            attacks.append(aid.strip())

    # Compute retreat obligations and gate from the resolution outcome.
    prev_ro = hx0.get("retreat_obligations")
    ro: dict[str, int] = dict(prev_ro) if isinstance(prev_ro, dict) else {}
    retreat_distance = ctx.resolution.retreat_distance
    retreat_unit_id: str | None = (
        str(ctx.resolution.retreat_unit_id).strip()
        if ctx.resolution.retreat_unit_id
        else None
    )
    gate: str | None = None
    if outcome in ("attacker_retreat", "defender_retreat"):
        if retreat_distance is None:
            raise ValueError("retreat_distance is required for retreat outcomes")
        if retreat_unit_id is None:
            retreat_unit_id = (
                str(ctx.attack_context.attacker_unit_id)
                if outcome == "attacker_retreat"
                else str(ctx.attack_context.defender_unit_id)
            )
        u0 = ctx.state.board.units.get(retreat_unit_id)
        if u0 is not None and u0.active:
            for u in ctx.state.board.active_units_at_hex(u0.position):
                if u.faction == u0.faction:
                    ro[str(u.unit_id)] = int(retreat_distance)
        gate = GATE_AWAITING_RETREAT
    elif outcome in ("none", "defender_destroyed"):
        gate = None
    else:
        raise ValueError(f"Unknown engine outcome {outcome!r}")

    # If defenders were destroyed, ensure they are not still present in obligations.
    if outcome == "defender_destroyed":
        for did in d_ids:
            if isinstance(did, str) and did.strip():
                ro.pop(did.strip(), None)

    # Build a stable last_combat payload for UI and post-combat interactions.
    def_hex = ctx.attack_context.defender_hex
    last_combat: dict[str, Any] = {
        "attack_kind": str(ctx.attack_context.attack_kind),
        "outcome": outcome,
        "attacker_id": str(ctx.attack_context.attacker_unit_id),
        "attacker_ids": list(a_ids),
        "defender_id": str(ctx.attack_context.defender_unit_id),
        "defender_ids": list(d_ids),
        "defender_hex": {"i": int(def_hex.i), "j": int(def_hex.j), "k": int(def_hex.k)},
        "defender_hexes": [
            {"i": int(h.i), "j": int(h.j), "k": int(h.k)}
            for h in ctx.attack_context.defender_hexes
        ],
        "attacker_hexes": [
            {"i": int(h.i), "j": int(h.j), "k": int(h.k)}
            for h in ctx.attack_context.attacker_hexes
        ],
        "retreat_distance": retreat_distance,
        "retreat_unit_id": retreat_unit_id,
    }

    # Titles may use `effects.last_combat_patch` to annotate the base record.
    eff = ctx.resolution.effects
    if isinstance(eff, dict):
        patch = eff.get("last_combat_patch")
        if isinstance(patch, dict):
            last_combat = {**last_combat, **patch}

    patch: dict[str, Any] = {
        "attacks_this_phase": attacks,
        "retreat_obligations": ro,
        "last_combat": last_combat,
    }
    remove_keys: tuple[str, ...] = ()
    if gate:
        patch["combat_gate"] = gate
    else:
        remove_keys = ("combat_gate",)
    actions.append(
        PatchTitleBucket(
            ctx.extension_key,
            patch,
            remove_keys=remove_keys,
        )
    )

    # Optional hexdemo follow-up: allow disrupt-instead gate when a retreat is pending.
    if isinstance(eff, dict):
        retreat_meta = eff.get("retreat")
        if isinstance(retreat_meta, dict) and retreat_meta.get("allow_disrupt_instead"):
            # Only open the optional gate when we are actually in the retreat gate.
            if gate == GATE_AWAITING_RETREAT:
                actions.append(
                    PatchTitleBucket(
                        ctx.extension_key,
                        {"combat_gate": GATE_AWAITING_RETREAT_OR_DISRUPT},
                    )
                )

    return actions


def on_retreat_obligation_cleared(
    ctx: RetreatObligationClearedContext,
) -> list[StateAction]:
    """Open optional post-retreat advance when hexdemo rules match."""

    return combat_actions.maybe_open_advance_after_retreat(
        ctx.state, ctx.extension_key
    )


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
    "PHASE_SCOPED_COMBAT_KEYS",
    "attack_planning_blocked_reason",
    "blocks_routine_phase_advance",
    "clear_combat_state_actions",
    "current_combat_gate",
    "dock_arc_hint",
    "follow_up_after_attack",
    "on_retreat_obligation_cleared",
]
