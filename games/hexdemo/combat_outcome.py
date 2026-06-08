"""
Hexdemo combat outcome builder (post-attack session-state handoff to the combat arc).
"""

from __future__ import annotations

from typing import Any

from hexengine.hooks.attack import AfterAttackAppliedContext
from hexengine.hooks.bucket import BucketPatch
from hexengine.hooks.combat_outcome import CombatOutcome

from . import title_state


def build_combat_outcome_after_applied(
    ctx: AfterAttackAppliedContext,
) -> CombatOutcome:
    """Record session follow-up after a committed attack (retreat duties, phase tracking)."""

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
        last_combat_patch = eff.get("last_combat_patch")
        if isinstance(last_combat_patch, dict):
            last_combat = {**last_combat, **last_combat_patch}

    values: dict[str, Any] = {
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
            values["disrupt_instead_offered"] = True
            remove_keys = ()

    return CombatOutcome(patch=BucketPatch(values=values, remove_keys=remove_keys))


__all__ = ["build_combat_outcome_after_applied"]
