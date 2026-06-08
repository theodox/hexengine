"""Tests for combat interaction message hooks."""

from __future__ import annotations

from games.hexdemo import combat_transitions

from hexengine.arcs import ArcCursor, with_arc_cursor
from hexengine.hooks.ui_combat_messages import (
    CombatInteractionMessagesContext,
    default_combat_interaction_messages,
    retreat_owner_faction,
)
from hexengine.state import GameState


def test_retreat_owner_faction_defender() -> None:
    from hexengine.hexes.types import Hex
    from hexengine.state.game_state import BoardState, UnitState

    board = BoardState(
        units={
            "a": UnitState(
                unit_id="a",
                unit_type="t",
                faction="union",
                position=Hex(0, 0, 0),
                active=True,
            ),
            "d": UnitState(
                unit_id="d",
                unit_type="t",
                faction="confederate",
                position=Hex(1, 0, -1),
                active=True,
            ),
        }
    )
    st = GameState(board=board, turn=GameState.create_empty().turn)
    assert retreat_owner_faction(st, "defender_retreat", "a", "d") == "confederate"


def test_default_combat_interaction_messages_advance_row_uses_segment() -> None:
    st = GameState.create_empty().with_title_state(
        {"advance": {"faction": "union"}},
        title_bucket_key="hexdemo",
    )
    st = with_arc_cursor(
        st,
        ArcCursor(arc_id="combat", segment_id="advance_gate"),
    )
    segment = {
        "schema": 1,
        "arc_id": "combat",
        "segment_id": "advance_gate",
        "ui_mode": combat_transitions.GATE_AWAITING_ADVANCE,
        "owner": "union",
        "allowed_actions": ["CombatAdvance", "CombatDeclineAdvance"],
        "action_locus": {},
    }
    ctx = CombatInteractionMessagesContext(
        state=st,
        viewer_faction="union",
        extension_key="hexdemo",
        current_segment=segment,
    )
    rows = default_combat_interaction_messages(
        ctx,
        combat_instruction=lambda _o, _r: ("resolved", "ok"),
        advance_gate_banners=lambda _f: ("Advance now", "Wait"),
    )
    kinds = [r.kind for r in rows]
    assert "advance" in kinds
