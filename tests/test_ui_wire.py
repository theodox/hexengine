"""Presentation DTOs and ui_wire adapter."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = str(REPO_ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from hexengine.authoring.present import (
    inform_popup,
    panel_action,
    turn_dock_panel,
)
from hexengine.hooks.internal.ui_wire import (
    inform_popup_to_wire,
    turn_action_dock_to_wire,
)
from hexengine.ui.display import TurnDockPanel


def test_turn_dock_panel_to_wire_dict() -> None:
    panel = turn_dock_panel(
        presentation_id="attack_ready",
        headline="Combat",
        actions=(
            panel_action(
                id="end_phase",
                action_type="NextPhase",
                label="End Phase",
                enabled=True,
            ),
        ),
        host="advance",
        css_class="hexdemo-turn-dock hexdemo-turn-dock--attack_ready",
    )
    wire = panel.to_wire_dict()
    assert wire["schema"] == 1
    assert wire["dock_arc"] == "attack_ready"
    assert wire["host"] == "advance"
    assert wire["actions"][0]["id"] == "end_phase"


def test_turn_action_dock_to_wire_accepts_dto_and_dict() -> None:
    dto = turn_dock_panel(
        presentation_id="hidden",
        actions=(),
        headline="",
    )
    legacy = {"schema": 1, "id": "legacy", "host": "user-controls", "actions": []}
    out = turn_action_dock_to_wire([dto, legacy])
    assert len(out) == 2
    assert out[0]["dock_arc"] == "hidden"
    assert out[1]["id"] == "legacy"


def test_inform_popup_to_wire_accepts_dto_and_dict() -> None:
    dto = inform_popup(text="hello", ttl_ms=750)
    assert inform_popup_to_wire(dto)["ttl_ms"] == 750
    assert inform_popup_to_wire({"text": "x", "kind": "info", "ttl_ms": 100})[
        "ttl_ms"
    ] == 100


def test_hexdemo_turn_action_dock_returns_dtos() -> None:
    GAMES = str(REPO_ROOT / "games")
    if GAMES not in sys.path:
        sys.path.insert(0, GAMES)

    from games.hexdemo.hooks.turn_action_dock import turn_action_dock_for_viewer
    from hexengine.hooks.ui import TurnActionDockContext
    from hexengine.state import GameState

    ctx = TurnActionDockContext(
        state=GameState.create_empty(),
        viewer_faction="union",
        extension_key="hexdemo",
        shell_ui={},
        schedule_index=0,
        current_faction="union",
        current_phase="Combat",
        phase_actions_remaining=2,
        viewer_is_turn_owner=True,
        client_contract_features=frozenset(),
    )
    panels = turn_action_dock_for_viewer(ctx)
    assert len(panels) == 1
    assert isinstance(panels[0], TurnDockPanel)
    wire = turn_action_dock_to_wire(panels)[0]
    assert wire["id"] == "turn_actions"
    assert isinstance(wire.get("dock_arc"), str) and wire["dock_arc"]
