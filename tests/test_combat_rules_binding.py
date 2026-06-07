"""CombatRulesBinding scaffold and arc spec helper."""

from __future__ import annotations

import pytest
from games.template.combat_arc import BINDING, TemplateCombatRules

from hexengine.authoring.patterns.combat import (
    SEG_ATTACK,
    SEG_CLASSIFY,
    CombatArcGateKinds,
    combat_rules_binding_missing_methods,
    combat_rules_binding_satisfies,
    combat_rules_binding_to_arc_spec,
)


def test_template_binding_satisfies_protocol() -> None:
    assert combat_rules_binding_satisfies(TemplateCombatRules())
    assert combat_rules_binding_satisfies(BINDING)
    assert combat_rules_binding_missing_methods(BINDING) == ()


def test_combat_rules_binding_to_arc_spec_builds_valid_arc() -> None:
    gates = CombatArcGateKinds(
        awaiting_retreat="awaiting_retreat",
        awaiting_retreat_or_disrupt="awaiting_retreat_or_disrupt",
        awaiting_advance="awaiting_advance",
    )
    spec = combat_rules_binding_to_arc_spec(BINDING, gates)
    spec.arc.validate()
    assert spec.arc.entry == SEG_CLASSIFY

    with_attack = combat_rules_binding_to_arc_spec(
        BINDING,
        gates,
        attack_effect=lambda _ctx: [],
    )
    assert with_attack.arc.get(SEG_ATTACK).allowed_actions == frozenset({"Attack"})


def test_binding_missing_methods_reported() -> None:
    class Incomplete:
        def validate_attack(self, _ctx):
            return None

    missing = combat_rules_binding_missing_methods(Incomplete())
    assert "resolve_attack" in missing
    assert "has_pending_retreat" in missing


def test_combat_rules_binding_to_arc_spec_rejects_incomplete() -> None:
    class Incomplete:
        pass

    with pytest.raises(TypeError, match="missing methods"):
        combat_rules_binding_to_arc_spec(
            Incomplete(),
            CombatArcGateKinds("r", "rod", "a"),
        )
