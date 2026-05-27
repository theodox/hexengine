"""
Hexdemo combat gate and obligation follow-ups after the engine applies an attack.

Phase C wires `AttackHook.AFTER_ATTACK_APPLIED` here; gate constants and a fuller
transition table land in phase D of `docs/ENGINE_BOUNDARY_2_PLAN.md`.
"""

from __future__ import annotations

from hexengine.hooks.attack import AfterAttackAppliedContext
from hexengine.state.action_manager import StateAction


def follow_up_after_attack(_ctx: AfterAttackAppliedContext) -> list[StateAction]:
    """Title-owned follow-ups after ``Attack`` and ``ApplyCombatEffects``."""
    return []


__all__ = ["follow_up_after_attack"]
