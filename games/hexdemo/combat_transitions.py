"""
Hexdemo combat gate and obligation transitions (title-owned policy).

Engine ``Attack`` / ``ApplyCombatEffects`` still apply core outcomes; this module
returns follow-up ``StateAction``s and advance-gate policy via attack hooks.
"""

from __future__ import annotations

from hexengine.hooks.attack import (
    AfterAttackAppliedContext,
    RetreatObligationClearedContext,
)
from hexengine.hooks.internal.advance import default_maybe_open_combat_advance_after_retreat
from hexengine.state.action_manager import StateAction
from hexengine.state.actions import OpenCombatAdvance, PatchTitleBucket

from . import title_state

GATE_AWAITING_RETREAT = "awaiting_retreat"
GATE_AWAITING_RETREAT_OR_DISRUPT = "awaiting_retreat_or_disrupt"


def follow_up_after_attack(ctx: AfterAttackAppliedContext) -> list[StateAction]:
    """Title-owned follow-ups after ``Attack`` and ``ApplyCombatEffects``."""

    actions: list[StateAction] = []
    eff = ctx.resolution.effects
    if isinstance(eff, dict):
        retreat_meta = eff.get("retreat")
        if (
            isinstance(retreat_meta, dict)
            and retreat_meta.get("allow_disrupt_instead")
            and str(title_state.bucket(ctx.state).get("combat_gate", "")).strip()
            == GATE_AWAITING_RETREAT
        ):
            actions.append(
                PatchTitleBucket(
                    ctx.extension_key,
                    {"combat_gate": GATE_AWAITING_RETREAT_OR_DISRUPT},
                )
            )
    return actions


def on_retreat_obligation_cleared(
    ctx: RetreatObligationClearedContext,
) -> OpenCombatAdvance | None:
    """Open optional post-retreat advance when engine default rules match."""

    return default_maybe_open_combat_advance_after_retreat(ctx.state, ctx.extension_key)


__all__ = [
    "GATE_AWAITING_RETREAT",
    "GATE_AWAITING_RETREAT_OR_DISRUPT",
    "follow_up_after_attack",
    "on_retreat_obligation_cleared",
]
