"""Thin ``MovementHook`` adapters — policy lives in ``movement_rules.py``."""

from __future__ import annotations

from hexengine.hooks.movement import MovementHook
from hexengine.hooks.wiring import bind_title_hook

from .. import movement_rules


@bind_title_hook(MovementHook.MOVEMENT_STEP_COST_FOR_UNIT)
def movement_step_cost_for_unit(state, unit_id, from_hex, to_hex, base_cost):
    return movement_rules.movement_step_cost_for_unit(
        state, unit_id, from_hex, to_hex, base_cost
    )


@bind_title_hook(MovementHook.MOVEMENT_BUDGET_FOR_UNIT)
def movement_budget_for_unit(state, unit_id):
    return movement_rules.movement_budget_for_unit(state, unit_id)


@bind_title_hook(MovementHook.ZOC_HEXES_FOR_UNIT)
def zoc_hexes_for_unit(state, unit_id):
    return movement_rules.zoc_hexes_for_unit(state, unit_id)


@bind_title_hook(MovementHook.RETREAT_OBLIGATION_HEXES_REMAINING)
def retreat_obligation_hexes_remaining(state, unit_id):
    return movement_rules.retreat_obligation_hexes_remaining(state, unit_id)


@bind_title_hook(MovementHook.ANY_RETREAT_OBLIGATION_PENDING)
def any_retreat_obligation_pending(state):
    return movement_rules.any_retreat_obligation_pending(state)


@bind_title_hook(MovementHook.FACTION_HAS_PENDING_RETREAT_OBLIGATION)
def faction_has_pending_retreat_obligation(state, faction):
    return movement_rules.faction_has_pending_retreat_obligation(state, faction)


@bind_title_hook(MovementHook.RETREAT_BLOCKED_HEXES)
def retreat_blocked_hexes(state, unit_id):
    return movement_rules.retreat_blocked_hexes(state, unit_id)


@bind_title_hook(MovementHook.VALIDATE_RETREAT_MOVE)
def validate_retreat_move(ctx, hexes_remaining):
    return movement_rules.validate_retreat_move(ctx, hexes_remaining)


@bind_title_hook(MovementHook.RETREAT_PATH_PREVIEW)
def retreat_path_preview_for_viewer(ctx):
    from ..retreat_path_preview import retreat_path_preview

    return retreat_path_preview(ctx)


@bind_title_hook(MovementHook.AUTO_ADVANCE_PHASE_AFTER_MOVE_SPEND)
def auto_advance_phase_after_move_spend(state):
    return movement_rules.auto_advance_phase_after_move_spend(state)
