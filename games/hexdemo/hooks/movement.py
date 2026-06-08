"""Wire ``MovementHook`` slots to ``movement.rules.BINDING``."""

from __future__ import annotations

from ..movement.rules import BINDING

_MOVEMENT_SLOTS = (
    "movement_step_cost_for_unit",
    "movement_budget_for_unit",
    "zoc_hexes_for_unit",
    "retreat_obligation_hexes_remaining",
    "any_retreat_obligation_pending",
    "faction_has_pending_retreat_obligation",
    "retreat_blocked_hexes",
    "validate_retreat_move",
    "auto_advance_phase_after_move_spend",
)

MOVEMENT_HOOKS = {name: getattr(BINDING, name) for name in _MOVEMENT_SLOTS}


def retreat_path_preview_for_viewer(ctx):
    from ..movement.retreat_preview import retreat_path_preview  # breaks cycle: movement → retreat_preview → movement

    return retreat_path_preview(ctx)


MOVEMENT_HOOKS["retreat_path_preview"] = retreat_path_preview_for_viewer


__all__ = ["MOVEMENT_HOOKS", "retreat_path_preview_for_viewer"]
