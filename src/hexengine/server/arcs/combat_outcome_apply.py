"""
Apply title combat outcomes after ``Attack`` + ``ApplyCombatEffects``.
"""

from __future__ import annotations

from ...hooks.attack import AfterAttackAppliedContext, AttackResolution
from ...hooks.combat_outcome import CombatOutcome
from ...hooks.core import ENGINE_DEFAULT
from ...hooks.title import TitleHooks
from ...state.action_manager import StateAction


def split_resolve_result(
    raw: AttackResolution | CombatOutcome | object,
) -> tuple[AttackResolution, CombatOutcome | None]:
    """
    Normalize ``resolve_attack`` return value.

    ``CombatOutcome`` with ``resolution`` may carry an optional pre-built bucket patch.
    """

    if raw is ENGINE_DEFAULT:
        raise ValueError("This game title does not resolve Attack actions")
    if isinstance(raw, CombatOutcome):
        if raw.resolution is None:
            raise TypeError("CombatOutcome from resolve_attack must include resolution")
        return raw.resolution, raw
    if isinstance(raw, AttackResolution):
        return raw, None
    raise TypeError(
        "resolve_attack must return AttackResolution, CombatOutcome, or "
        "hooks.ENGINE_DEFAULT"
    )


def follow_up_state_actions_after_attack(
    hooks: TitleHooks,
    ctx: AfterAttackAppliedContext,
    *,
    outcome_from_resolve: CombatOutcome | None = None,
) -> list[StateAction]:
    """
    Collect post-attack bucket follow-up actions.

    Priority: ``CombatOutcome`` from ``resolve_attack``, then
    ``COMBAT_OUTCOME_AFTER_APPLIED``.
    """

    if outcome_from_resolve is not None:
        return outcome_from_resolve.follow_up_state_actions(ctx.session_state_key)

    raw_outcome = hooks.attack.build_combat_outcome_after_applied(ctx)
    if raw_outcome is ENGINE_DEFAULT:
        return []
    if not isinstance(raw_outcome, CombatOutcome):
        raise TypeError(
            "hooks.attack.combat_outcome_after_applied must return "
            "CombatOutcome or hooks.ENGINE_DEFAULT"
        )
    return raw_outcome.follow_up_state_actions(ctx.session_state_key)


__all__ = [
    "follow_up_state_actions_after_attack",
    "split_resolve_result",
]
