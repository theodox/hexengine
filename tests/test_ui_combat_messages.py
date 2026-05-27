"""Tests for combat interaction message hooks (engine boundary phase B)."""

from __future__ import annotations

from hexengine.hooks.ui import CombatInteractionContext
from hexengine.hooks.ui_combat_messages import (
    CombatInteractionMessagesContext,
    default_blocks_routine_phase_advance,
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
    assert (
        retreat_owner_faction(st, "defender_retreat", "a", "d") == "confederate"
    )


def test_default_blocks_routine_phase_advance_gate() -> None:
    st = GameState.create_empty().with_extension(
        {"hexdemo": {"combat_gate": "awaiting_advance"}}
    )
    assert default_blocks_routine_phase_advance(st, "hexdemo") is True


def test_default_blocks_routine_phase_advance_retreat_obligation() -> None:
    st = GameState.create_empty().with_extension(
        {"hexdemo": {"retreat_obligations": {"u1": 2}}}
    )
    assert default_blocks_routine_phase_advance(st, "hexdemo") is True


def test_default_combat_interaction_messages_advance_row() -> None:
    st = GameState.create_empty().with_extension(
        {
            "hexdemo": {
                "combat_gate": "awaiting_advance",
                "advance": {"faction": "union"},
            }
        }
    )
    ctx = CombatInteractionMessagesContext(
        state=st, viewer_faction="union", extension_key="hexdemo"
    )
    rows = default_combat_interaction_messages(
        ctx,
        combat_instruction=lambda _o, _r: ("resolved", "ok"),
        advance_gate_banners=lambda _f: ("Advance now", "Wait"),
    )
    kinds = [r["kind"] for r in rows]
    assert "advance" in kinds
