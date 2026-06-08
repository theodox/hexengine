"""Hexdemo presentation/interaction_messages copy."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GAMES = str(REPO_ROOT / "games")
if GAMES not in sys.path:
    sys.path.insert(0, GAMES)

from hexdemo.presentation.interaction_messages import (
    advance_gate_banners_for_viewer,
    combat_instruction_for_viewer,
)
from hexengine.hooks.ui import AdvanceGateInteractionContext, CombatInteractionContext
from hexengine.state import GameState


def test_combat_instruction_retreat_owner_gets_required() -> None:
    ctx = CombatInteractionContext(
        state=GameState.create_empty(),
        viewer_faction="confederate",
        outcome="defender_retreat",
        retreat_owner_faction="confederate",
    )
    kind, text = combat_instruction_for_viewer(ctx)
    assert kind == "retreat_required"
    assert "Mandatory retreat" in text


def test_combat_instruction_shell_ui_override() -> None:
    ctx = CombatInteractionContext(
        state=GameState.create_empty(),
        viewer_faction="union",
        outcome="none",
        retreat_owner_faction=None,
    )
    kind, text = combat_instruction_for_viewer(
        ctx, shell_ui={"combat_outcome_none": "All quiet."}
    )
    assert kind == "resolved"
    assert text == "All quiet."


def test_combat_interaction_messages_hook_uses_ctx_shell_ui() -> None:
    from games.hexdemo.hooks.ui import combat_interaction_messages

    st = GameState.create_empty()
    st = GameState(
        board=st.board,
        turn=st.turn,
        session_state={
            "last_combat": {
                "outcome": "none",
                "attacker_id": "a",
                "defender_id": "d",
            }
        },
        session_state_key="hexdemo",
        rng_log=(),
    )
    from hexengine.hooks.ui_combat_messages import CombatInteractionMessagesContext

    rows = combat_interaction_messages(
        CombatInteractionMessagesContext(
            state=st,
            viewer_faction="union",
            session_state_key="hexdemo",
            shell_ui={"combat_outcome_none": "Quiet round."},
        )
    )
    assert any(r.text == "Quiet round." for r in rows)


def test_advance_gate_banners_shell_ui() -> None:
    ctx = AdvanceGateInteractionContext(
        state=GameState.create_empty(),
        viewer_faction="union",
        advancing_faction="union",
    )
    adv, wait = advance_gate_banners_for_viewer(
        ctx, shell_ui={"combat_advance_prompt": "Go now."}
    )
    assert adv == "Go now."
    assert "Waiting" in wait
