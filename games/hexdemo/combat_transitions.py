"""
Hexdemo combat transition effects (title-owned).

Maintains the ``combat_gate`` bucket mirror for debugging and title-local guards.
The engine reads ``current_segment``, not bucket gate strings.

State table (``combat_gate`` in the title bucket — effect-maintained mirror; engine
legality reads ``current_segment``, not this field):

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

# Wire values stored in the title bucket ``combat_gate`` key (effect-maintained mirror).
GATE_AWAITING_RETREAT = "awaiting_retreat"
GATE_AWAITING_RETREAT_OR_DISRUPT = "awaiting_retreat_or_disrupt"
GATE_AWAITING_ADVANCE = "awaiting_advance"

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

def current_combat_gate(state: GameState) -> str:
    """Normalized ``combat_gate`` mirror in the title bucket (``""`` if unset)."""

    return str(title_state.bucket(state).get("combat_gate", "")).strip()


def attack_planning_blocked_reason(
    state: GameState, player_faction: str
) -> str | None:
    """Human-readable block reason for attack plan preview, or ``None`` if allowed."""

    if str(player_faction).strip() != str(state.turn.current_faction).strip():
        return "Not your turn"
    phase = str(state.turn.current_phase).strip()
    if phase not in ("Combat", "Attack"):
        return "Attack planning is only available during Combat"

    from .arc_segment import project_segment_for_faction

    from hexengine.arcs.segment_wire import (
        KIND_DOCK_ARC_ADVANCE,
        KIND_DOCK_ARC_RETREAT,
        segment_allows_action,
    )

    seg = project_segment_for_faction(state, player_faction)
    if seg is not None:
        if segment_allows_action(seg, "Attack"):
            return None
        kind = str(seg.get("kind", "")).strip()
        if kind in KIND_DOCK_ARC_ADVANCE:
            return "Resolve combat advance before planning an attack"
        if kind in KIND_DOCK_ARC_RETREAT:
            return "Resolve retreat before planning an attack"
        return "Combat obligations must be resolved before planning an attack"

    if combat.any_retreat_obligation_pending(state):
        return "Resolve retreat before planning an attack"
    return None


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
    attacks = list(title_state.attacks_this_phase(ctx.state))
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
    "GATE_AWAITING_ADVANCE",
    "GATE_AWAITING_RETREAT",
    "GATE_AWAITING_RETREAT_OR_DISRUPT",
    "GATES_BLOCKING_ROUTINE",
    "PHASE_SCOPED_COMBAT_KEYS",
    "attack_planning_blocked_reason",
    "clear_combat_state_actions",
    "current_combat_gate",
    "follow_up_after_attack",
    "on_retreat_obligation_cleared",
]
