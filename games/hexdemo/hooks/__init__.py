"""
Hexdemo hook implementations.

This is game-authored policy code. The engine calls these via `TitleHooks`.
"""

from __future__ import annotations

from hexengine.hooks import AttackHooks, MovementHooks, TitleHooks, UIHooks

from . import attack, movement, overlays, ui


def build_hooks() -> TitleHooks:
    return TitleHooks(
        movement=MovementHooks(
            zoc_hexes_for_unit=movement.zoc_hexes_for_unit,
            stacking_policy_for_unit=movement.stacking_policy_for_unit,
            stacking_limit=lambda _state: 3,
            retreat_obligation_hexes_remaining=movement.retreat_obligation_hexes_remaining,
            any_retreat_obligation_pending=movement.any_retreat_obligation_pending,
            faction_has_pending_retreat_obligation=movement.faction_has_pending_retreat_obligation,
            retreat_blocked_hexes=movement.retreat_blocked_hexes,
            validate_retreat_move=movement.validate_retreat_move,
        ),
        attack=AttackHooks(
            validate_attack=attack.validate_attack,
            resolve_attack=attack.resolve_attack,
            auto_advance_phase_after_attack=attack.auto_advance_phase_after_attack,
        ),
        ui=UIHooks(
            popup_message=ui.popup_message,
            map_overlays=overlays.map_overlays,
        ),
    )


__all__ = ["build_hooks"]

