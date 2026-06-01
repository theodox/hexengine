"""Combat cleanup arc pattern (authoring.patterns.combat)."""

from __future__ import annotations

from hexengine.arcs import CURRENT, NO_OWNER, OwnerRef
from hexengine.authoring.patterns.combat import (
    CombatArcGateKinds,
    OWNER_RETREATING,
    SEG_ADVANCE_GATE,
    SEG_CLASSIFY,
    SEG_RETREAT_GATE,
    build_combat_cleanup_arc,
)
from games.hexdemo import combat_arc, combat_transitions


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
    gates = CombatArcGateKinds(
        awaiting_retreat="awaiting_retreat",
        awaiting_retreat_or_disrupt="awaiting_retreat_or_disrupt",
        awaiting_advance="awaiting_advance",
    )
    build_combat_cleanup_arc(_StubEffects(), gates)


def test_combat_cleanup_pattern_segment_owners() -> None:
    gates = CombatArcGateKinds(
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
    """Hexdemo binding produces the same graph as calling the pattern directly."""

    from games.hexdemo.combat_arc import (
        _HEXDEMO_COMBAT_EFFECTS,
        _HEXDEMO_COMBAT_GATES,
    )

    from_pattern = build_combat_cleanup_arc(_HEXDEMO_COMBAT_EFFECTS, _HEXDEMO_COMBAT_GATES)
    from_hexdemo = combat_arc.build_combat_arc()
    assert from_pattern == from_hexdemo


def test_hexdemo_gate_kinds_on_segments() -> None:
    a = combat_arc.build_combat_arc()
    by_kind = {seg.kind: seg.id for seg in a.segments if seg.kind}
    assert by_kind[combat_transitions.GATE_AWAITING_RETREAT] == SEG_RETREAT_GATE
