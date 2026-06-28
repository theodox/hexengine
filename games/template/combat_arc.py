"""
Template combat scaffold (copy when enabling combat + extension key).

Wire ``ArcHook.COMBAT_ARC`` in ``arcs/wiring.py`` (or ``hooks/__init__.py`` via ``build_hooks``) after you set
``session_state_key``, add combat schedule slots, interaction hooks, segment registry
rows, and ``attack_effect`` on the arc spec. For a visible graph, copy
``games/hexdemo/combat/graph.py`` — see ``games/template/combat/graph.py`` (outline).
Until then this module is reference-only.
"""

from __future__ import annotations

from hexengine.arcs import ArcContext
from hexengine.authoring.patterns.combat import (
    COMBAT_ARC_ID,
    CombatArcGateUiModes,
    combat_rules_binding_to_arc_spec,
)
from hexengine.hooks.interaction import (
    AfterAttackAppliedContext,
    AttackContext,
    AttackResolution,
    CombatAdvanceMoveContext,
)
from hexengine.hooks.bucket import BucketPatch
from hexengine.hooks.combat_outcome import CombatOutcome
from hexengine.state.action_manager import StateAction


class TemplateCombatRules:
    """
    Minimal no-cleanup combat binding for new titles.

    Replace stubs with real CRT/outcome logic and arc guards/effects as rules grow.
    """

    def validate_attack(self, ctx: AttackContext) -> None:
        return None

    def resolve_attack(self, ctx: AttackContext) -> AttackResolution:
        return AttackResolution(outcome="none")

    def combat_outcome_after_applied(
        self, ctx: AfterAttackAppliedContext
    ) -> CombatOutcome:
        return CombatOutcome(patch=BucketPatch())

    def detect_combat_advance_move(self, ctx: CombatAdvanceMoveContext) -> bool:
        return False

    def has_pending_retreat(self, ctx: ArcContext) -> bool:
        return False

    def disrupt_offered(self, ctx: ArcContext) -> bool:
        return False

    def advance_available(self, ctx: ArcContext) -> bool:
        return False

    def is_retreat_fulfillment(self, ctx: ArcContext) -> bool:
        return False

    def is_combat_advance_move(self, ctx: ArcContext) -> bool:
        return False

    def apply_retreat_step(self, ctx: ArcContext) -> list[StateAction]:
        return []

    def disrupt_instead(self, ctx: ArcContext) -> list[StateAction]:
        return []

    def open_advance(self, ctx: ArcContext) -> list[StateAction]:
        return []

    def resolve_advance(self, ctx: ArcContext) -> list[StateAction]:
        return []

    def clear_advance_gate(self, ctx: ArcContext) -> list[StateAction]:
        return []


_TEMPLATE_GATES = CombatArcGateUiModes(
    awaiting_retreat="awaiting_retreat",
    awaiting_retreat_or_disrupt="awaiting_retreat_or_disrupt",
    awaiting_advance="awaiting_advance",
)

BINDING = TemplateCombatRules()


def build_template_combat_arc_spec():
    """Example ``ArcSpec`` — bind via ``ArcHook.COMBAT_ARC`` when combat is enabled."""

    return combat_rules_binding_to_arc_spec(
        BINDING, _TEMPLATE_GATES, arc_id=COMBAT_ARC_ID
    )


__all__ = [
    "BINDING",
    "TemplateCombatRules",
    "build_template_combat_arc_spec",
]
