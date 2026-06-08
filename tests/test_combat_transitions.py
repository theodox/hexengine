"""Combat transition helpers (effects + segment-aware policy)."""

from __future__ import annotations

from dataclasses import replace

from games.hexdemo import combat_transitions
from games.hexdemo.arc_segment import phase_advance_blocked

from hexengine.arcs import ArcCursor, with_arc_cursor
from hexengine.state import GameState


def test_phase_advance_blocked_on_combat_retreat_segment() -> None:
    st = GameState.create_empty().with_session_state_key("hexdemo")
    st = with_arc_cursor(st, ArcCursor(arc_id="combat", segment_id="retreat_gate"))
    assert phase_advance_blocked(st) is True


def test_phase_advance_allowed_on_routine_move_segment() -> None:
    st = GameState.create_empty().with_session_state_key("hexdemo")
    st = with_arc_cursor(st, ArcCursor(arc_id="union_move", segment_id="routine"))
    assert phase_advance_blocked(st) is False


def test_segment_registry_maps_retreat_gate_kind() -> None:
    from games.hexdemo.segment_ui import resolve_presentation_id

    segment = {
        "schema": 1,
        "ui_mode": combat_transitions.GATE_AWAITING_RETREAT_OR_DISRUPT,
        "allowed_actions": ["CombatDisruptInsteadOfRetreat"],
    }
    assert (
        resolve_presentation_id(
            segment,
            viewer_may_act=True,
            current_phase="Combat",
        )
        == "retreat_gate"
    )


def test_attack_planning_blocked_on_advance_segment() -> None:
    base = GameState.create_empty()
    st = base.with_turn(
        replace(
            base.turn,
            current_faction="union",
            current_phase="Combat",
            phase_actions_remaining=1,
        )
    ).with_session_state_key("hexdemo")
    st = with_arc_cursor(st, ArcCursor(arc_id="combat", segment_id="advance_gate"))
    reason = combat_transitions.attack_planning_blocked_reason(st, "union")
    assert reason is not None
    assert "advance" in reason.lower()
