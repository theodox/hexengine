"""
Hexdemo combat transition effects (title-owned).

Combat flow legality and affordances read ``current_segment`` (declared arcs).
Bucket keys ``retreat_obligations``, ``advance``, ``last_combat``, and
``disrupt_instead_offered`` hold match data; segment ``kind`` strings match
``GATE_AWAITING_*`` constants below.

State table (segment ``kind`` on the combat arc cursor):

| Kind | End phase / auto-advance | Attack planning | Typical entry |
|------|--------------------------|-----------------|---------------|
| (routine) | allowed when no retreat obligations | allowed | turn combat slot |
| ``awaiting_retreat`` | blocked | blocked | ``Attack`` retreat outcome |
| ``awaiting_retreat_or_disrupt`` | blocked | blocked | optional disrupt CRT |
| ``awaiting_advance`` | blocked | blocked | post-retreat advance window |

Transitions:

- retreat outcome → obligations + combat arc ``awaiting_retreat`` (classify)
- optional disrupt CRT → ``disrupt_instead_offered`` flag (classify → disrupt gate)
- obligations cleared + policy → ``advance`` payload (classify → advance gate)
- advance move or skip → arc done
"""

from __future__ import annotations

from typing import Any

from hexengine.hooks.attack import AfterAttackAppliedContext
from hexengine.state import GameState
from hexengine.state.action_manager import StateAction
from hexengine.state.actions import PatchTitleBucket

from . import combat_actions, title_state

# Segment ``kind`` values on gate-bearing combat arc segments.
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

# Title bucket keys cleared on phase advance (`after_phase_transition`).
# ``combat_gate`` is legacy-only (retired mirror); still removed so old saves stay clean.
PHASE_SCOPED_COMBAT_KEYS: tuple[str, ...] = (
    "attacks_this_phase",
    "retreat_obligations",
    "combat_gate",
    "disrupt_instead_offered",
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


def attack_planning_blocked_reason(
    state: GameState, player_faction: str
) -> str | None:
    """Human-readable block reason for attack plan preview, or ``None`` if allowed."""

    if str(player_faction).strip() != str(state.turn.current_faction).strip():
        return "Not your turn"
    phase = str(state.turn.current_phase).strip()
    if phase not in ("Combat", "Attack"):
        return "Attack planning is only available during Combat"

    from . import arc_segment

    from hexengine.arcs.segment_wire import (
        KIND_DOCK_ARC_ADVANCE,
        KIND_DOCK_ARC_RETREAT,
        segment_allows_action,
    )

    seg = arc_segment.project_segment_for_faction(state, player_faction)
    if seg is None:
        return None
    if segment_allows_action(seg, "Attack"):
        return None
    kind = str(seg.get("kind", "")).strip()
    if kind in KIND_DOCK_ARC_ADVANCE:
        return "Resolve combat advance before planning an attack"
    if kind in KIND_DOCK_ARC_RETREAT:
        return "Resolve retreat before planning an attack"
    return "Combat obligations must be resolved before planning an attack"


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

    attacks = list(title_state.attacks_this_phase(ctx.state))
    for aid in a_ids:
        if isinstance(aid, str) and aid.strip():
            attacks.append(aid.strip())

    prev_ro = title_state.retreat_obligations(ctx.state)
    ro: dict[str, int] = dict(prev_ro) if prev_ro else {}
    retreat_distance = ctx.resolution.retreat_distance
    retreat_unit_id: str | None = (
        str(ctx.resolution.retreat_unit_id).strip()
        if ctx.resolution.retreat_unit_id
        else None
    )
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
    elif outcome not in ("none", "defender_destroyed"):
        raise ValueError(f"Unknown engine outcome {outcome!r}")

    if outcome == "defender_destroyed":
        for did in d_ids:
            if isinstance(did, str) and did.strip():
                ro.pop(did.strip(), None)

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

    eff = ctx.resolution.effects
    if isinstance(eff, dict):
        patch = eff.get("last_combat_patch")
        if isinstance(patch, dict):
            last_combat = {**last_combat, **patch}

    bucket_patch: dict[str, Any] = {
        "attacks_this_phase": attacks,
        "retreat_obligations": ro,
        "last_combat": last_combat,
    }
    remove_keys: tuple[str, ...] = ("disrupt_instead_offered",)

    if isinstance(eff, dict):
        retreat_meta = eff.get("retreat")
        if (
            isinstance(retreat_meta, dict)
            and retreat_meta.get("allow_disrupt_instead")
            and ro
        ):
            bucket_patch["disrupt_instead_offered"] = True
            remove_keys = ()

    actions.append(
        PatchTitleBucket(
            ctx.extension_key,
            bucket_patch,
            remove_keys=remove_keys,
        )
    )

    return actions


__all__ = [
    "GATE_AWAITING_ADVANCE",
    "GATE_AWAITING_RETREAT",
    "GATE_AWAITING_RETREAT_OR_DISRUPT",
    "GATES_BLOCKING_ROUTINE",
    "PHASE_SCOPED_COMBAT_KEYS",
    "attack_planning_blocked_reason",
    "clear_combat_state_actions",
    "follow_up_after_attack",
]
