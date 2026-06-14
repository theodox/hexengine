"""Thin ``ModificationHook`` adapters — policy lives in ``movement/rules.py``."""

from __future__ import annotations

from hexengine.hooks.modification import ModificationHook
from hexengine.hooks.wiring import bind_title_hook

from ..movement import rules as movement_rules


@bind_title_hook(ModificationHook.MOVEMENT_STEP_COST_FOR_UNIT)
def movement_step_cost_for_unit(state, unit_id, from_hex, to_hex, base_cost):
    return movement_rules.movement_step_cost_for_unit(
        state, unit_id, from_hex, to_hex, base_cost
    )


@bind_title_hook(ModificationHook.MOVEMENT_BUDGET_FOR_UNIT)
def movement_budget_for_unit(state, unit_id):
    return movement_rules.movement_budget_for_unit(state, unit_id)


@bind_title_hook(ModificationHook.ZOC_HEXES_FOR_UNIT)
def zoc_hexes_for_unit(state, unit_id):
    return movement_rules.zoc_hexes_for_unit(state, unit_id)


@bind_title_hook(ModificationHook.RETREAT_OBLIGATION_HEXES_REMAINING)
def retreat_obligation_hexes_remaining(state, unit_id):
    return movement_rules.retreat_obligation_hexes_remaining(state, unit_id)


@bind_title_hook(ModificationHook.ANY_RETREAT_OBLIGATION_PENDING)
def any_retreat_obligation_pending(state):
    return movement_rules.any_retreat_obligation_pending(state)


@bind_title_hook(ModificationHook.FACTION_HAS_PENDING_RETREAT_OBLIGATION)
def faction_has_pending_retreat_obligation(state, faction):
    return movement_rules.faction_has_pending_retreat_obligation(state, faction)


@bind_title_hook(ModificationHook.RETREAT_BLOCKED_HEXES)
def retreat_blocked_hexes(state, unit_id):
    return movement_rules.retreat_blocked_hexes(state, unit_id)


@bind_title_hook(ModificationHook.VALIDATE_RETREAT_MOVE)
def validate_retreat_move(ctx, hexes_remaining):
    return movement_rules.validate_retreat_move(ctx, hexes_remaining)


@bind_title_hook(ModificationHook.AUTO_ADVANCE_PHASE_AFTER_MOVE_SPEND)
def auto_advance_phase_after_move_spend(state):
    return movement_rules.auto_advance_phase_after_move_spend(state)


@bind_title_hook(ModificationHook.RETREAT_PATH_PREVIEW)
def retreat_path_preview(ctx):
    from ..movement.retreat_preview import (
        retreat_path_preview as compute_retreat_path_preview,
    )

    return compute_retreat_path_preview(ctx)


__all__ = [
    "any_retreat_obligation_pending",
    "auto_advance_phase_after_move_spend",
    "faction_has_pending_retreat_obligation",
    "movement_budget_for_unit",
    "movement_step_cost_for_unit",
    "retreat_blocked_hexes",
    "retreat_obligation_hexes_remaining",
    "retreat_path_preview",
    "validate_retreat_move",
    "zoc_hexes_for_unit",
]
