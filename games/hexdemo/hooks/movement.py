from __future__ import annotations

from hexengine.hooks import StackingPolicy
from hexengine.hexes.types import Hex
from hexengine.hexes.math import distance
from hexengine.state import GameState
from hexengine.state.logic import adjacent_enemy_zoc_hexes
from hexengine.state.logic import retreat_impassable_enemy_zoc_hexes

from .. import combat


def movement_budget_for_unit(state: GameState, unit_id: str) -> float:
    u = state.board.units.get(unit_id)
    if u is None:
        raise ValueError(f"Unknown unit {unit_id!r}")
    raw = u.attributes.get("movement")
    if raw is not None:
        return float(raw)
    # Fallback: schedule budget is published separately; this hook is intended
    # primarily for per-unit overrides via attributes.
    return 0.0


def zoc_hexes_for_unit(state: GameState, unit_id: str) -> frozenset[Hex]:
    return adjacent_enemy_zoc_hexes(state, unit_id)


def stacking_policy_for_unit(state: GameState, unit_id: str) -> StackingPolicy:
    # Hexdemo rule: allow pass-through of friendly stacks; limit only applies at rest.
    return StackingPolicy(limit=3, friendly_pass_through=True, friendly_end_allowed=True)


def retreat_obligation_hexes_remaining(state: GameState, unit_id: str) -> int | None:
    return combat.retreat_hexes_remaining(state, unit_id)


def any_retreat_obligation_pending(state: GameState) -> bool:
    return combat.any_retreat_obligation_pending(state)


def faction_has_pending_retreat_obligation(state: GameState, faction: str) -> bool:
    return combat.faction_has_pending_retreat(state, faction)


def retreat_blocked_hexes(state: GameState, unit_id: str) -> frozenset[Hex]:
    # Hexdemo retreat routing rule: enemy ZOC blocks retreat unless overlapped by friendly ZOC.
    # Use the title ZOC ring (adjacent-enemy) as the "enemy ring" input.
    enemy_ring = adjacent_enemy_zoc_hexes(state, unit_id)
    return retreat_impassable_enemy_zoc_hexes(state, unit_id, enemy_zoc_ring=enemy_ring)


def validate_retreat_move(ctx, hexes_remaining: int) -> None:
    leg = distance(ctx.from_hex, ctx.to_hex)
    if leg != int(hexes_remaining):
        raise ValueError(
            f"Retreat move must cover exactly {int(hexes_remaining)} hexes (cube distance); got {leg}"
        )

