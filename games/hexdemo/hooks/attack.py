from __future__ import annotations

import random

from hexengine.hexes.math import distance
from hexengine.hexes.los import has_line_of_sight
from hexengine.hooks import AttackContext, AttackResolution

from .. import combat
from ..constants import PACK_STATE_EXTENSION_KEY


def _terrain_blocks_los(ctx: AttackContext):
    board = ctx.state.board

    def blocks(h):
        loc = board.effective_location(h)
        if loc is None:
            return False
        return bool(getattr(loc, "block_los", False))

    return blocks


def _enemy_defender_ids_on_hex(ctx: AttackContext) -> tuple[str, ...]:
    """
    Hexdemo rule: an attack applies to every active enemy unit on the defender hex.
    """
    attacker = ctx.state.board.units.get(ctx.attacker_unit_id)
    if attacker is None or not attacker.active:
        return ()
    out: list[str] = []
    for u in ctx.state.board.active_units_at_hex(ctx.defender_hex):
        if u.faction != attacker.faction:
            out.append(str(u.unit_id))
    return tuple(out)


def validate_attack(ctx: AttackContext) -> None:
    if ctx.attack_kind not in ("combined",):
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
    raw_attacker_ids = ctx.params.get("attacker_ids")
    attacker_ids: list[str] = []
    if isinstance(raw_attacker_ids, list) and raw_attacker_ids:
        for uid in raw_attacker_ids:
            if isinstance(uid, str) and uid.strip():
                attacker_ids.append(uid.strip())
    if not attacker_ids:
        attacker_ids = [ctx.attacker_unit_id]

    target_hex = ctx.defender_hex
    blocks = _terrain_blocks_los(ctx)
    for aid in attacker_ids:
        a = ctx.state.board.units.get(aid)
        if a is None or not a.active:
            raise ValueError("Invalid attacker")
        if a.faction != ctx.player_faction:
            raise ValueError("You do not control the attacker")
        if a.faction == defender.faction:
            raise ValueError("Cannot attack same faction")
        ut = str(a.unit_type).lower()
        dist = distance(a.position, target_hex)
        if ut in ("infantry", "inf"):
            if dist != 1:
                raise ValueError("Infantry attacker is not adjacent to the target")
        elif ut in ("artillery", "art"):
            raw_range = a.attributes.get("range")
            try:
                atk_range = int(raw_range) if raw_range is not None else 0
            except Exception:
                atk_range = 0
            if atk_range <= 1:
                raise ValueError("Artillery has no ranged capability")
            if not (dist > 1 and dist <= atk_range):
                raise ValueError("Artillery target is out of range")
            if not has_line_of_sight(a.position, target_hex, blocks=blocks):
                raise ValueError("No line of sight to target")
        else:
            raise ValueError(f"Unit type {ut!r} cannot participate in combined attacks")

    # Hexdemo stack-wide: must have at least one enemy defender on the target hex.
    defender_ids = _enemy_defender_ids_on_hex(ctx)
    if not defender_ids:
        raise ValueError("No enemy units on target hex")

    # Preserve existing hexdemo behavior (attack-once per combat segment).
    hx = ctx.state.extension.get(PACK_STATE_EXTENSION_KEY)
    if isinstance(hx, dict):
        prev = hx.get("attacks_this_phase")
        if isinstance(prev, list):
            for aid in attacker_ids:
                if aid in prev:
                    raise ValueError("That unit has already attacked this combat phase")


def resolve_attack(ctx: AttackContext) -> AttackResolution:
    if ctx.attack_kind not in ("combined",):
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

    raw_attacker_ids = ctx.params.get("attacker_ids")
    attacker_ids: list[str] = []
    if isinstance(raw_attacker_ids, list) and raw_attacker_ids:
        for uid in raw_attacker_ids:
            if isinstance(uid, str) and uid.strip():
                attacker_ids.append(uid.strip())
    if not attacker_ids:
        attacker_ids = [ctx.attacker_unit_id]

    defender_ids = _enemy_defender_ids_on_hex(ctx)
    if not defender_ids:
        # Should have been rejected by validate_attack; keep deterministic failure.
        raise ValueError("No enemy units on target hex")

    rng_entry = {
        "op": "combined_attack",
        "outcome": outcome,
        "attacker_id": ctx.attacker_unit_id,
        "attacker_ids": list(attacker_ids),
        "defender_id": ctx.defender_unit_id,
        "defender_ids": list(defender_ids),
        "retreat_distance": retreat_distance,
    }
    return AttackResolution(
        outcome=outcome,
        attacker_ids=tuple(attacker_ids),
        defender_ids=defender_ids,
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

