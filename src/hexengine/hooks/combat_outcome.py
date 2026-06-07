"""
Title combat outcome: bucket follow-up after ``Attack`` + ``ApplyCombatEffects``.

``CombatOutcome`` is the author-facing shape for match-state updates that feed combat
arc classify (``retreat_obligations``, ``last_combat``, etc.). The engine applies it as
``PatchTitleBucket`` actions during the attack commit path (arc ``attack`` segment or
authority attack assembly), before classify auto-advances cleanup segments.

Titles may return ``CombatOutcome`` (with embedded ``AttackResolution``) from
``resolve_attack``, or bind ``AttackHook.COMBAT_OUTCOME_AFTER_APPLIED`` to build an
outcome from ``AfterAttackAppliedContext`` after board effects commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..state.action_manager import StateAction
from ..state.actions import PatchTitleBucket
from .attack import AttackResolution


@dataclass(frozen=True, slots=True)
class CombatOutcome:
    """
    Title bucket patch applied after ``Attack`` and ``ApplyCombatEffects``.

    When returned from ``resolve_attack``, ``resolution`` must be set so the engine can
    build the ``Attack`` state action. When built from ``AfterAttackAppliedContext``,
    ``resolution`` is omitted and only ``bucket_patch`` / ``remove_keys`` are used.
    """

    bucket_patch: dict[str, Any]
    remove_keys: tuple[str, ...] = ()
    resolution: AttackResolution | None = None

    def follow_up_state_actions(self, extension_key: str) -> list[StateAction]:
        """Undoable title-bucket mutations for the combat arc handoff."""

        return [
            PatchTitleBucket(
                str(extension_key),
                dict(self.bucket_patch),
                remove_keys=self.remove_keys,
            )
        ]


__all__ = ["CombatOutcome"]
