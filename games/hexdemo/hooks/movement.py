from __future__ import annotations

from hexengine.hexes.math import distance
from hexengine.hexes.types import Hex
from hexengine.hooks.movement import ENGINE_DEFAULT, MovementHook
from hexengine.hooks.wiring import bind_title_hook
from hexengine.state import (
    GameState,
    edge_movement_extra_for_neighbor_step,
    linear_features_on_neighbor_step,
    min_linear_movement_cost_for_tags,
)
from hexengine.state.logic import (
    adjacent_enemy_zoc_hexes,
    retreat_impassable_enemy_zoc_hexes,
)

from .. import combat


@bind_title_hook(MovementHook.MOVEMENT_STEP_COST_FOR_UNIT)
def movement_step_cost_for_unit(
    state: GameState, unit_id: str, from_hex: Hex, to_hex: Hex, base_cost: float
) -> float:
    tags_on_step: list[str] = []
    for lf in linear_features_on_neighbor_step(state.board, from_hex, to_hex):
        tags_on_step.extend(lf.tags)
    linear = (
        min_linear_movement_cost_for_tags(state.board, tags_on_step)
        if tags_on_step
        else None
    )
    step_base = float(linear) if linear is not None else base_cost
    return step_base + edge_movement_extra_for_neighbor_step(
        state.board, from_hex, to_hex
    )


@bind_title_hook(MovementHook.MOVEMENT_BUDGET_FOR_UNIT)
def movement_budget_for_unit(state: GameState, unit_id: str) -> float | object:
    u = state.board.units.get(unit_id)
    if u is None:
        raise ValueError(f"Unknown unit {unit_id!r}")
    raw = u.attributes.get("movement")
    if raw is not None:
        return float(raw)
    # Let the server use `DEFAULT_MOVEMENT_BUDGET` / schedule scalar — never return 0.0
    # here: if this hook is wired on `MovementHooks`, 0.0 makes every move unreachable.
    return ENGINE_DEFAULT


@bind_title_hook(MovementHook.ZOC_HEXES_FOR_UNIT)
def zoc_hexes_for_unit(state: GameState, unit_id: str) -> frozenset[Hex]:
    return adjacent_enemy_zoc_hexes(state, unit_id)


@bind_title_hook(MovementHook.RETREAT_OBLIGATION_HEXES_REMAINING)
def retreat_obligation_hexes_remaining(state: GameState, unit_id: str) -> int | None:
    return combat.retreat_hexes_remaining(state, unit_id)


@bind_title_hook(MovementHook.ANY_RETREAT_OBLIGATION_PENDING)
def any_retreat_obligation_pending(state: GameState) -> bool:
    return combat.any_retreat_obligation_pending(state)


@bind_title_hook(MovementHook.FACTION_HAS_PENDING_RETREAT_OBLIGATION)
def faction_has_pending_retreat_obligation(state: GameState, faction: str) -> bool:
    return combat.faction_has_pending_retreat(state, faction)


@bind_title_hook(MovementHook.RETREAT_BLOCKED_HEXES)
def retreat_blocked_hexes(state: GameState, unit_id: str) -> frozenset[Hex]:
    # Hexdemo retreat routing rule: enemy ZOC blocks retreat unless overlapped by friendly ZOC.
    # Use the title ZOC ring (adjacent-enemy) as the "enemy ring" input.
    enemy_ring = adjacent_enemy_zoc_hexes(state, unit_id)
    return retreat_impassable_enemy_zoc_hexes(state, unit_id, enemy_zoc_ring=enemy_ring)


@bind_title_hook(MovementHook.VALIDATE_RETREAT_MOVE)
def validate_retreat_move(ctx, hexes_remaining: int) -> None:
    leg = distance(ctx.from_hex, ctx.to_hex)
    if leg != int(hexes_remaining):
        raise ValueError(
            f"Retreat move must cover exactly {int(hexes_remaining)} hexes (cube distance); got {leg}"
        )


@bind_title_hook(MovementHook.RETREAT_PATH_PREVIEW)
def retreat_path_preview_for_viewer(ctx):
    from ..retreat_path_preview import retreat_path_preview

    return retreat_path_preview(ctx)


@bind_title_hook(MovementHook.AUTO_ADVANCE_PHASE_AFTER_MOVE_SPEND)
def auto_advance_phase_after_move_spend(state: GameState) -> bool:
    """Advance when actions are depleted unless the active segment blocks routine advance."""

    from ..arc_segment import phase_advance_blocked

    if phase_advance_blocked(state):
        return False
    return int(state.turn.phase_actions_remaining) <= 0
