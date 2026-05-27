"""Tests for interaction panels (Track B catalog) and turn action dock (hexdemo)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hexengine.hooks.ui_interaction_panels import (
    InteractionPanelsContext,
    default_interaction_panels_for_viewer,
)
from hexengine.state import GameState
from hexengine.ui.display import interaction_panel, panel_input

REPO_ROOT = Path(__file__).resolve().parents[1]


def _ensure_games_on_path() -> None:
    import sys

    games = str(REPO_ROOT / "games")
    if games not in sys.path:
        sys.path.insert(0, games)


def test_default_interaction_panels_empty_without_actions() -> None:
    st = GameState.create_empty()
    ctx = InteractionPanelsContext(
        state=st,
        viewer_faction="union",
        extension_key="hexdemo",
        shell_ui={},
        primary_actions=(),
    )
    assert default_interaction_panels_for_viewer(ctx) == []


def test_default_interaction_panels_wraps_primary_actions() -> None:
    st = GameState.create_empty()
    actions = (
        {
            "schema": 1,
            "id": "combat_advance",
            "action_type": "CombatAdvance",
            "label": "Advance",
            "enabled": True,
        },
    )
    ctx = InteractionPanelsContext(
        state=st,
        viewer_faction="union",
        extension_key="hexdemo",
        shell_ui={},
        primary_actions=actions,
    )
    rows = default_interaction_panels_for_viewer(ctx)
    assert len(rows) == 1
    assert rows[0]["id"] == "primary_actions"
    assert rows[0]["host"] == "user-controls"
    assert rows[0]["actions"] == list(actions)


def test_interaction_panel_and_panel_input_helpers() -> None:
    row = interaction_panel(
        id="p1",
        html="<p>hint</p>",
        actions=[{"schema": 1, "id": "a1", "action_type": "X", "label": "Go", "enabled": True}],
        inputs=[panel_input(id="mode", kind="select", label="Mode", options=({"value": "a", "label": "A"},))],
    )
    assert row["html"] == "<p>hint</p>"
    assert row["actions"][0]["id"] == "a1"
    assert row["inputs"][0]["kind"] == "select"


def test_hexdemo_turn_action_dock_gate_hint_html_escapes() -> None:
    """Gate arcs use ``dock_gate_panel_hint`` + dock_gate template."""
    _ensure_games_on_path()
    from games.hexdemo.hooks.turn_action_dock import turn_action_dock_for_viewer
    from hexengine.hooks.ui import TurnActionDockContext
    from hexengine.hexes.types import Hex
    from hexengine.state.game_state import BoardState, TurnState, UnitState

    st = GameState.create_empty()
    ext = {
        "hexdemo": {
            "combat_gate": "awaiting_advance",
            "advance": {"faction": "union"},
        }
    }
    board = BoardState(
        units={
            "u1": UnitState(
                unit_id="u1",
                unit_type="inf",
                faction="union",
                position=Hex(0, 0, 0),
                health=10,
                active=True,
            ),
        }
    )
    turn = TurnState(
        current_faction="union",
        current_phase="Combat",
        phase_actions_remaining=1,
        turn_number=st.turn.turn_number,
        schedule_index=st.turn.schedule_index,
        global_tick=st.turn.global_tick,
    )
    st = GameState(
        board=board,
        turn=turn,
        title_state=ext.get("hexdemo", {}),
        title_bucket_key="hexdemo",
        rng_log=(),
    )
    ctx = TurnActionDockContext(
        state=st,
        viewer_faction="union",
        extension_key="hexdemo",
        shell_ui={"dock_gate_panel_hint": "Pick an option<script>"},
        schedule_index=0,
        current_faction="union",
        current_phase="Combat",
        phase_actions_remaining=1,
        viewer_is_turn_owner=True,
        client_contract_features=frozenset(),
    )
    rows = turn_action_dock_for_viewer(ctx)
    assert len(rows) == 1
    assert rows[0]["id"] == "turn_actions"
    assert rows[0]["dock_arc"] == "advance_gate"
    html = str(rows[0].get("html", ""))
    assert "Pick an option" in html
    assert "<script>" not in html
