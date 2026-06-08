"""Context-manager arc builder and its typed sugars (composable arcs, step 0c).

These tests double as the worked example: they show how a title declares a real combat
arc with the builder, and assert the builder emits exactly the canonical spec data.
"""

from __future__ import annotations

import pytest

from hexengine.arcs import (
    AUTO,
    CURRENT,
    NO_OWNER,
    Arc,
    Event,
    FlowEnd,
    Goto,
    Interrupt,
    OwnerRef,
    Segment,
    Transition,
)
from hexengine.authoring import arc, case


# Dummy effects/guards stand in for real StateAction-returning hooks; identity matters,
# so they are module-level (not lambdas) where a test compares them.
def _apply_attack(ctx):
    return []


def _do_retreat(ctx):
    return []


def _defender_eliminated(ctx) -> bool:
    return True


# ---- The worked example: a combat arc ---------------------------------------


def build_combat_arc() -> Arc:
    """Attack, then a retreat interrupt owned by the defender, then an advance gate."""

    with arc("combat") as a:  # entry defaults to the first segment ("attack")
        with a.segment("attack", owner=CURRENT, ui_mode="routine") as s:
            s.on(
                "Attack",
                interrupt="retreat_gate",
                resume_at="advance_gate",
                effect=_apply_attack,
            )
        with a.segment(
            "retreat_gate", owner=OwnerRef("retreating"), ui_mode="retreat_gate"
        ) as s:
            s.on("RetreatUnit", resume=True, effect=_do_retreat)
            s.on("DisruptInsteadOfRetreat", resume=True)
        with a.segment("advance_gate", owner=CURRENT, ui_mode="advance_gate") as s:
            s.on("CombatAdvance", done=True)
            s.on("DeclineAdvance", done=True)
    return a.build()


def test_combat_arc_builds_and_validates() -> None:
    build_combat_arc()  # build() validates by default


def test_entry_defaults_to_first_segment() -> None:
    assert build_combat_arc().entry == "attack"


def test_allowed_actions_are_derived_not_declared() -> None:
    a = build_combat_arc()
    assert a.get("attack").allowed_actions == frozenset({"Attack"})
    assert a.get("retreat_gate").allowed_actions == frozenset(
        {"RetreatUnit", "DisruptInsteadOfRetreat"}
    )
    assert a.get("advance_gate").allowed_actions == frozenset(
        {"CombatAdvance", "DeclineAdvance"}
    )


def test_interrupt_and_resume_targets() -> None:
    a = build_combat_arc()
    attack_t = a.get("attack").transitions[0]
    assert attack_t.target == Interrupt(segment="retreat_gate", resume="advance_gate")
    assert attack_t.effect is _apply_attack

    retreat = a.get("retreat_gate")
    assert all(t.target is FlowEnd.RESUME for t in retreat.transitions)
    assert retreat.transitions[0].effect is _do_retreat

    advance = a.get("advance_gate")
    assert all(t.target is FlowEnd.DONE for t in advance.transitions)


def test_builder_emits_canonical_spec_data() -> None:
    """The builder is sugar only: its output equals the hand-written spec exactly."""

    built = build_combat_arc()
    hand = Arc(
        id="combat",
        entry="attack",
        segments=(
            Segment(
                id="attack",
                owner=CURRENT,
                ui_mode="routine",
                transitions=(
                    Transition(
                        trigger=Event("Attack"),
                        target=Interrupt("retreat_gate", "advance_gate"),
                        effect=_apply_attack,
                    ),
                ),
            ),
            Segment(
                id="retreat_gate",
                owner=OwnerRef("retreating"),
                ui_mode="retreat_gate",
                transitions=(
                    Transition(
                        trigger=Event("RetreatUnit"),
                        target=FlowEnd.RESUME,
                        effect=_do_retreat,
                    ),
                    Transition(
                        trigger=Event("DisruptInsteadOfRetreat"),
                        target=FlowEnd.RESUME,
                    ),
                ),
            ),
            Segment(
                id="advance_gate",
                owner=CURRENT,
                ui_mode="advance_gate",
                transitions=(
                    Transition(trigger=Event("CombatAdvance"), target=FlowEnd.DONE),
                    Transition(trigger=Event("DeclineAdvance"), target=FlowEnd.DONE),
                ),
            ),
        ),
    )
    assert built == hand


# ---- branch / auto_branch / case sugar --------------------------------------


def test_auto_branch_builds_guarded_automatic_transitions() -> None:
    with arc("resolve", entry="resolve") as a:
        with a.segment("resolve", owner=NO_OWNER) as s:
            s.auto_branch(
                case(guard=_defender_eliminated, goto="advance"),
                case(goto="cleanup"),  # default arm, no guard
            )
        with a.segment("advance", owner=CURRENT) as s:
            s.on("CombatAdvance", done=True)
        with a.segment("cleanup", owner=NO_OWNER) as s:
            s.auto(done=True)
    built = a.build()

    resolve = built.get("resolve")
    assert [t.trigger for t in resolve.transitions] == [AUTO, AUTO]
    assert resolve.transitions[0].guard is _defender_eliminated
    assert resolve.transitions[0].target == Goto("advance")
    assert resolve.transitions[1].guard is None
    assert resolve.transitions[1].target == Goto("cleanup")


def test_branch_builds_guarded_event_transitions() -> None:
    with arc("a", entry="s") as bld:
        with bld.segment("s", owner=CURRENT) as s:
            s.branch(
                "Resolve",
                case(guard=_defender_eliminated, done=True),
                case(goto="s"),
            )
    built = bld.build()
    s = built.get("s")
    assert all(t.trigger == Event("Resolve") for t in s.transitions)
    assert s.transitions[0].target is FlowEnd.DONE
    assert s.transitions[1].target == Goto("s")


# ---- target-keyword validation ----------------------------------------------


def test_on_requires_exactly_one_target() -> None:
    with arc("a", entry="s") as bld:
        with pytest.raises(ValueError, match="exactly one target"):
            with bld.segment("s", owner=CURRENT) as s:
                s.on("X")  # no target


def test_on_rejects_two_targets() -> None:
    with arc("a", entry="s") as bld:
        with pytest.raises(ValueError, match="exactly one target"):
            with bld.segment("s", owner=CURRENT) as s:
                s.on("X", goto="s", done=True)


def test_interrupt_requires_resume_at() -> None:
    with arc("a", entry="s") as bld:
        with pytest.raises(ValueError, match="resume_at"):
            with bld.segment("s", owner=CURRENT) as s:
                s.on("X", interrupt="other")


def test_resume_at_without_interrupt_rejected() -> None:
    with arc("a", entry="s") as bld:
        with pytest.raises(ValueError, match="only valid together with interrupt"):
            with bld.segment("s", owner=CURRENT) as s:
                s.on("X", done=True, resume_at="other")


def test_build_propagates_validation_errors() -> None:
    # advance_gate references a non-existent goto target -> Arc.validate raises.
    with arc("bad", entry="s") as a:
        with a.segment("s", owner=CURRENT) as s:
            s.on("X", goto="ghost")
    with pytest.raises(ValueError, match="goto"):
        a.build()
