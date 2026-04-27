from __future__ import annotations

import random

from hexengine.hexes.math import distance
from hexengine.hooks import AttackContext, AttackResolution

from .. import combat
from ..constants import PACK_STATE_EXTENSION_KEY


def validate_attack(ctx: AttackContext) -> None:
    if ctx.attack_kind != "adjacent":
        raise ValueError(f"Unknown attack_kind for hexdemo: {ctx.attack_kind!r}")
    phase = str(ctx.state.turn.current_phase)
    if phase not in ("Combat", "Attack"):
        raise ValueError("Attacks are only allowed during the combat phase")
    if ctx.player_faction != ctx.state.turn.current_faction:
        raise ValueError("Not your turn")
    if combat.any_retreat_obligation_pending(ctx.state):
        raise ValueError("Resolve retreat before issuing another attack")

    attacker = ctx.state.board.units.get(ctx.attacker_unit_id)
    defender = ctx.state.board.units.get(ctx.defender_unit_id)
    if attacker is None or not attacker.active:
        raise ValueError("Invalid attacker")
    if defender is None or not defender.active:
        raise ValueError("Invalid defender")
    if attacker.faction != ctx.player_faction:
        raise ValueError("You do not control the attacker")
    if attacker.faction == defender.faction:
        raise ValueError("Cannot attack same faction")
    if distance(attacker.position, defender.position) != 1:
        raise ValueError("Defender is not adjacent to the attacker")

    # Preserve existing hexdemo behavior (attack-once per combat segment).
    hx = ctx.state.extension.get(PACK_STATE_EXTENSION_KEY)
    if isinstance(hx, dict):
        prev = hx.get("attacks_this_phase")
        if isinstance(prev, list) and ctx.attacker_unit_id in prev:
            raise ValueError("That unit has already attacked this combat phase")


def resolve_attack(ctx: AttackContext) -> AttackResolution:
    if ctx.attack_kind != "adjacent":
        raise ValueError(f"Unknown attack_kind for hexdemo: {ctx.attack_kind!r}")

    outcome = random.choice(
        ("none", "attacker_retreat", "defender_retreat", "defender_destroyed")
    )
    retreat_distance = random.randint(1, 3) if outcome.endswith("retreat") else None
    retreat_unit_id: str | None = None
    if outcome == "attacker_retreat":
        retreat_unit_id = ctx.attacker_unit_id
    elif outcome == "defender_retreat":
        retreat_unit_id = ctx.defender_unit_id

    rng_entry = {
        "op": "adjacent_attack",
        "outcome": outcome,
        "attacker_id": ctx.attacker_unit_id,
        "defender_id": ctx.defender_unit_id,
        "retreat_distance": retreat_distance,
    }
    return AttackResolution(
        outcome=outcome,
        retreat_distance=retreat_distance,
        retreat_unit_id=retreat_unit_id,
        rng_entry=rng_entry,
    )


def auto_advance_phase_after_attack(state) -> bool:
    """
    Advance the schedule when every active unit of the current faction has attacked
    this combat segment and no mandatory retreat is pending.
    """
    if combat.any_retreat_obligation_pending(state):
        return False
    phase = str(state.turn.current_phase)
    if phase not in ("Combat", "Attack"):
        return False
    faction = state.turn.current_faction
    active_ids = {
        u.unit_id for u in state.board.units.values() if u.active and u.faction == faction
    }
    if not active_ids:
        return True
    hx = state.extension.get(PACK_STATE_EXTENSION_KEY)
    if not isinstance(hx, dict):
        return False
    raw = hx.get("attacks_this_phase")
    if not isinstance(raw, list):
        return False
    attacked: set[str] = set()
    for uid in raw:
        if not isinstance(uid, str):
            continue
        u = state.board.units.get(uid)
        if u is not None and u.active and u.faction == faction:
            attacked.add(uid)
    return active_ids <= attacked

