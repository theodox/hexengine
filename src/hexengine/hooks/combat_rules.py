"""
Author-facing combat rules binding protocol.

One pack-root class (in ``combat_arc.py``) implements attack policy plus combat arc
guards/effects. Use ``combat_rules_binding_to_arc_spec`` to produce ``ArcSpec``; keep
``hooks/attack.py`` thin during migration.
"""

from __future__ import annotations

from typing import Protocol

from ..arcs.spec import ArcContext
from ..state.action_manager import StateAction
from .attack import (
    AfterAttackAppliedContext,
    AttackContext,
    AttackResolution,
    CombatAdvanceMoveContext,
)
from .combat_outcome import CombatOutcome
from .movement_rules import MovementRulesBinding


class CombatArcRulesBinding(Protocol):
    """Cleanup guards and effects wired into the declared combat arc."""

    def has_pending_retreat(self, ctx: ArcContext) -> bool: ...

    def disrupt_offered(self, ctx: ArcContext) -> bool: ...

    def advance_available(self, ctx: ArcContext) -> bool: ...

    def is_retreat_fulfillment(self, ctx: ArcContext) -> bool: ...

    def is_combat_advance_move(self, ctx: ArcContext) -> bool: ...

    def apply_retreat_step(self, ctx: ArcContext) -> list[StateAction]: ...

    def disrupt_instead(self, ctx: ArcContext) -> list[StateAction]: ...

    def open_advance(self, ctx: ArcContext) -> list[StateAction]: ...

    def resolve_advance(self, ctx: ArcContext) -> list[StateAction]: ...

    def clear_advance_gate(self, ctx: ArcContext) -> list[StateAction]: ...


class CombatRulesBinding(CombatArcRulesBinding, Protocol):
    """Full combat author surface: attack hooks + arc cleanup."""

    def validate_attack(self, ctx: AttackContext) -> None: ...

    def resolve_attack(
        self, ctx: AttackContext
    ) -> AttackResolution | CombatOutcome: ...

    def combat_outcome_after_applied(
        self, ctx: AfterAttackAppliedContext
    ) -> CombatOutcome | object: ...

    def detect_combat_advance_move(self, ctx: CombatAdvanceMoveContext) -> bool: ...


# Re-export movement binding for titles that colocate docs; movement stays separate.
__all__ = [
    "CombatArcRulesBinding",
    "CombatRulesBinding",
    "MovementRulesBinding",
]
