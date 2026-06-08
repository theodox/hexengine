"""
Combat follow-up after ``Attack`` + ``ApplyCombatEffects``.

``CombatOutcome`` carries a ``BucketPatch`` for session-state updates that feed combat
arc classify (``retreat_obligations``, ``last_combat``, etc.). The engine applies it as
``ApplyBucketPatch`` during the attack commit path (arc ``attack`` segment or authority
attack assembly), before classify auto-advances cleanup segments.

Titles may return ``CombatOutcome`` (with embedded ``AttackResolution``) from
``resolve_attack``, or bind ``AttackHook.COMBAT_OUTCOME_AFTER_APPLIED`` to build an
outcome from ``AfterAttackAppliedContext`` after board effects commit.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..state.action_manager import StateAction
from ..state.title_extension import BucketPatch
from .attack import AttackResolution


@dataclass(frozen=True, slots=True)
class CombatOutcome:
    """
    Session-state patch applied after ``Attack`` and ``ApplyCombatEffects``.

    When returned from ``resolve_attack``, ``resolution`` must be set so the engine can
    build the ``Attack`` state action. When built from ``AfterAttackAppliedContext``,
    ``resolution`` is omitted and only ``patch`` is used.
    """

    patch: BucketPatch
    resolution: AttackResolution | None = None

    def follow_up_state_actions(self, extension_key: str) -> list[StateAction]:
        """Undoable bucket mutations for the combat arc handoff."""

        return [self.patch.to_action(str(extension_key))]


__all__ = ["CombatOutcome"]
