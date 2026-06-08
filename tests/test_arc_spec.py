"""Declarative arc spec types and validation (composable arcs, step 0a)."""

from __future__ import annotations

import pytest

from hexengine.arcs import (
    AUTO,
    CURRENT,
    DONE,
    NO_OWNER,
    RESUME,
    Arc,
    AutoTrigger,
    Event,
    Faction,
    Goto,
    Interrupt,
    OwnerRef,
    Segment,
    Transition,
)


def _combat_like_arc() -> Arc:
    """A small combat-shaped arc mirroring the plan example (attack -> retreat -> advance).

    Uses dummy guard/effect callables; this step only exercises structure and validation.
    """

    return Arc(
        id="combat",
        entry="awaiting_retreat",
        segments=(
            Segment(
                id="awaiting_retreat",
                owner=OwnerRef("retreating"),
                ui_mode="retreat_gate",
                transitions=(
                    Transition(
                        trigger=Event("RetreatUnit"),
                        target=Goto("resolve_retreat"),
                        guard=lambda ctx: True,
                        effect=lambda ctx: [],
                    ),
                    Transition(
                        trigger=Event("DisruptInsteadOfRetreat"),
                        target=Goto("resolve_retreat"),
                    ),
                ),
            ),
            Segment(
                id="resolve_retreat",
                owner=NO_OWNER,
                transitions=(
                    Transition(trigger=AUTO, target=Goto("awaiting_advance")),
                ),
            ),
            Segment(
                id="awaiting_advance",
                owner=CURRENT,
                ui_mode="advance_gate",
                transitions=(
                    Transition(trigger=Event("CombatAdvance"), target=DONE),
                    Transition(trigger=Event("DeclineAdvance"), target=DONE),
                ),
            ),
        ),
    )


def test_validate_accepts_well_formed_arc() -> None:
    _combat_like_arc().validate()


def test_segment_allowed_actions_derived_from_event_triggers() -> None:
    arc = _combat_like_arc()
    assert arc.get("awaiting_retreat").allowed_actions == frozenset(
        {"RetreatUnit", "DisruptInsteadOfRetreat"}
    )
    assert arc.get("awaiting_advance").allowed_actions == frozenset(
        {"CombatAdvance", "DeclineAdvance"}
    )


def test_ownerless_segment_has_no_allowed_actions() -> None:
    seg = _combat_like_arc().get("resolve_retreat")
    assert seg.is_automatic is True
    assert seg.allowed_actions == frozenset()


def test_owned_segment_is_not_automatic() -> None:
    assert _combat_like_arc().get("awaiting_retreat").is_automatic is False


def test_get_and_by_id_round_trip() -> None:
    arc = _combat_like_arc()
    by_id = arc.by_id()
    assert set(by_id) == {"awaiting_retreat", "resolve_retreat", "awaiting_advance"}
    assert arc.get("resolve_retreat") is by_id["resolve_retreat"]
    with pytest.raises(KeyError):
        arc.get("missing")


def test_validate_rejects_empty_arc() -> None:
    with pytest.raises(ValueError, match="no segments"):
        Arc(id="empty", entry="x", segments=()).validate()


def test_validate_rejects_unknown_entry() -> None:
    arc = Arc(
        id="a",
        entry="nope",
        segments=(
            Segment(
                id="s",
                owner=CURRENT,
                transitions=(Transition(trigger=Event("X"), target=DONE),),
            ),
        ),
    )
    with pytest.raises(ValueError, match="entry"):
        arc.validate()


def test_validate_rejects_duplicate_segment_ids() -> None:
    seg = Segment(
        id="dup",
        owner=CURRENT,
        transitions=(Transition(trigger=Event("X"), target=DONE),),
    )
    with pytest.raises(ValueError, match="duplicate"):
        Arc(id="a", entry="dup", segments=(seg, seg)).validate()


def test_validate_rejects_segment_without_transitions() -> None:
    arc = Arc(
        id="a",
        entry="s",
        segments=(Segment(id="s", owner=CURRENT, transitions=()),),
    )
    with pytest.raises(ValueError, match="no transitions"):
        arc.validate()


def test_validate_rejects_unknown_goto_target() -> None:
    arc = Arc(
        id="a",
        entry="s",
        segments=(
            Segment(
                id="s",
                owner=CURRENT,
                transitions=(Transition(trigger=Event("X"), target=Goto("ghost")),),
            ),
        ),
    )
    with pytest.raises(ValueError, match="goto"):
        arc.validate()


def test_validate_rejects_unknown_interrupt_resume_target() -> None:
    arc = Arc(
        id="a",
        entry="s",
        segments=(
            Segment(
                id="s",
                owner=CURRENT,
                transitions=(
                    Transition(
                        trigger=Event("X"),
                        target=Interrupt(segment="sub", resume="ghost"),
                    ),
                ),
            ),
            Segment(
                id="sub",
                owner=CURRENT,
                transitions=(Transition(trigger=Event("Y"), target=RESUME),),
            ),
        ),
    )
    with pytest.raises(ValueError, match="resume"):
        arc.validate()


def test_validate_rejects_owned_segment_with_auto_trigger() -> None:
    arc = Arc(
        id="a",
        entry="s",
        segments=(
            Segment(
                id="s",
                owner=CURRENT,
                transitions=(Transition(trigger=AUTO, target=DONE),),
            ),
        ),
    )
    with pytest.raises(ValueError, match="Event triggers"):
        arc.validate()


def test_validate_rejects_ownerless_segment_with_event_trigger() -> None:
    arc = Arc(
        id="a",
        entry="s",
        segments=(
            Segment(
                id="s",
                owner=NO_OWNER,
                transitions=(Transition(trigger=Event("X"), target=DONE),),
            ),
        ),
    )
    with pytest.raises(ValueError, match="AUTO triggers"):
        arc.validate()


def test_faction_and_auto_trigger_identity() -> None:
    assert Faction("union").name == "union"
    assert AUTO is AutoTrigger.AUTO
