from __future__ import annotations

import random

from hexengine.hexes.los import has_line_of_sight
from hexengine.hexes.math import distance
from hexengine.hexes.types import Hex
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


def _expected_enemy_defender_ids(ctx: AttackContext) -> tuple[str, ...]:
    """Every active enemy unit on any ``ctx.defender_hexes`` cell."""
    attacker = ctx.state.board.units.get(ctx.attacker_unit_id)
    if attacker is None or not attacker.active:
        return ()
    out: list[str] = []
    seen: set[str] = set()
    for h in ctx.defender_hexes:
        for u in ctx.state.board.active_units_at_hex(h):
            if u.faction != attacker.faction and u.unit_id not in seen:
                seen.add(u.unit_id)
                out.append(str(u.unit_id))
    return tuple(sorted(out))


def _infantry_adjacent_to_any_defender_hex(a, defender_hexes: tuple[Hex, ...]) -> bool:
    return any(distance(a.position, h) == 1 for h in defender_hexes)


def _artillery_can_hit_any_defender_hex(
    a, defender_hexes: tuple[Hex, ...], blocks
) -> bool:
    raw_range = a.attributes.get("range")
    try:
        atk_range = int(raw_range) if raw_range is not None else 0
    except Exception:
        atk_range = 0
    if atk_range <= 1:
        return False
    for h in defender_hexes:
        dist = distance(a.position, h)
        if (
            dist > 1
            and dist <= atk_range
            and has_line_of_sight(a.position, h, blocks=blocks)
        ):
            return True
    return False


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

    att_primary = ctx.state.board.units.get(ctx.attacker_unit_id)
    if att_primary is None or not att_primary.active:
        raise ValueError("Invalid attacker")
    if att_primary.faction != ctx.player_faction:
        raise ValueError("You do not control the attacker")

    for did in ctx.defender_ids:
        d = ctx.state.board.units.get(did)
        if d is None or not d.active:
            raise ValueError("Invalid defender")
        if d.faction == att_primary.faction:
            raise ValueError("Cannot attack same faction")

    expected = set(_expected_enemy_defender_ids(ctx))
    if not expected:
        raise ValueError("No enemy units on defender hex(es)")
    if set(ctx.defender_ids) != expected:
        raise ValueError(
            "Defender list must include every enemy on the defender hex(es)"
        )

    defender_hexes = ctx.defender_hexes
    blocks = _terrain_blocks_los(ctx)
    for aid in ctx.attacker_ids:
        a = ctx.state.board.units.get(aid)
        if a is None or not a.active:
            raise ValueError("Invalid attacker")
        if a.faction != ctx.player_faction:
            raise ValueError("You do not control the attacker")
        ut = str(a.unit_type).lower()
        if ut in ("infantry", "inf"):
            if not _infantry_adjacent_to_any_defender_hex(a, defender_hexes):
                raise ValueError("Infantry attacker is not adjacent to the target")
        elif ut in ("artillery", "art"):
            if not _artillery_can_hit_any_defender_hex(a, defender_hexes, blocks):
                raise ValueError("No line of sight to target")
        else:
            raise ValueError(f"Unit type {ut!r} cannot participate in combined attacks")

    hx = ctx.state.extension.get(PACK_STATE_EXTENSION_KEY)
    if isinstance(hx, dict):
        prev = hx.get("attacks_this_phase")
        if isinstance(prev, list):
            for aid in ctx.attacker_ids:
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

    rng_entry = {
        "op": "combined_attack",
        "outcome": outcome,
        "attacker_id": ctx.attacker_unit_id,
        "attacker_ids": list(ctx.attacker_ids),
        "defender_id": ctx.defender_unit_id,
        "defender_ids": list(ctx.defender_ids),
        "retreat_distance": retreat_distance,
        "attacker_hexes": [
            {"i": int(h.i), "j": int(h.j), "k": int(h.k)} for h in ctx.attacker_hexes
        ],
        "defender_hexes": [
            {"i": int(h.i), "j": int(h.j), "k": int(h.k)} for h in ctx.defender_hexes
        ],
    }
    return AttackResolution(
        outcome=outcome,
        attacker_ids=None,
        defender_ids=None,
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
        u.unit_id
        for u in state.board.units.values()
        if u.active and u.faction == faction
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
