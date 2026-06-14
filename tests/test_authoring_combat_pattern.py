"""Combat cleanup arc pattern (authoring.patterns.combat)."""

from __future__ import annotations

from games.hexdemo.combat import arc as combat_arc
from games.hexdemo.combat import transitions as combat_transitions

from hexengine.arcs import CURRENT, NO_OWNER, OwnerRef
from hexengine.authoring.patterns.combat import (
    OWNER_RETREATING,
    SEG_ADVANCE_GATE,
    SEG_CLASSIFY,
    SEG_RETREAT_GATE,
    CombatArcGateUiModes,
    build_combat_cleanup_arc,
)


class _StubEffects:
    def has_pending_retreat(self, ctx):
        return False

    def disrupt_offered(self, ctx):
        return False

    def advance_available(self, ctx):
        return False

    def is_retreat_fulfillment(self, ctx):
        return False

    def is_combat_advance_move(self, ctx):
        return False

    def apply_retreat_step(self, ctx):
        return []

    def disrupt_instead(self, ctx):
        return []

    def open_advance(self, ctx):
        return []

    def resolve_advance(self, ctx):
        return []

    def clear_advance_gate(self, ctx):
        return []


def test_combat_cleanup_pattern_builds_and_validates() -> None:
    gates = CombatArcGateUiModes(
        awaiting_retreat="awaiting_retreat",
        awaiting_retreat_or_disrupt="awaiting_retreat_or_disrupt",
        awaiting_advance="awaiting_advance",
    )
    build_combat_cleanup_arc(_StubEffects(), gates)


def test_combat_cleanup_pattern_segment_owners() -> None:
    gates = CombatArcGateUiModes(
        awaiting_retreat="r",
        awaiting_retreat_or_disrupt="rod",
        awaiting_advance="a",
    )
    a = build_combat_cleanup_arc(_StubEffects(), gates)
    assert a.entry == SEG_CLASSIFY
    assert a.get(SEG_CLASSIFY).owner is NO_OWNER
    assert a.get(SEG_RETREAT_GATE).owner == OwnerRef(OWNER_RETREATING)
    assert a.get(SEG_ADVANCE_GATE).owner is CURRENT


def test_hexdemo_combat_arc_matches_pattern() -> None:
    """Hexdemo binding produces the same graph as calling the pattern helper."""

    from games.hexdemo.combat.arc import build_hexdemo_combat_arc_spec

    arc = build_hexdemo_combat_arc_spec().arc
    arc.validate()
    assert arc == combat_arc.build_combat_arc()


def test_hexdemo_combat_graph_matches_engine_pattern() -> None:
    """Pack ``graph.py`` stays aligned with ``build_combat_cleanup_arc``."""

    from games.hexdemo.combat import rules as combat_rules
    from games.hexdemo.combat.graph import build_hexdemo_combat_arc

    from hexengine.authoring.patterns.combat import combat_rules_effects_adapter

    gates = CombatArcGateUiModes(
        awaiting_retreat=combat_transitions.GATE_AWAITING_RETREAT,
        awaiting_retreat_or_disrupt=combat_transitions.GATE_AWAITING_RETREAT_OR_DISRUPT,
        awaiting_advance=combat_transitions.GATE_AWAITING_ADVANCE,
    )
    effects = combat_rules_effects_adapter(combat_rules.BINDING)
    pack_arc = build_hexdemo_combat_arc(
        effects,
        gates,
        attack_effect=combat_rules.BINDING.attack_arc_effect,
    )
    pattern_arc = build_combat_cleanup_arc(
        effects,
        gates,
        attack_effect=combat_rules.BINDING.attack_arc_effect,
    )
    assert pack_arc == pattern_arc


def test_hexdemo_gate_kinds_on_segments() -> None:
    a = combat_arc.build_combat_arc()
    by_kind = {seg.ui_mode: seg.id for seg in a.segments if seg.ui_mode}
    assert by_kind[combat_transitions.GATE_AWAITING_RETREAT] == SEG_RETREAT_GATE
