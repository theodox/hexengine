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
    interaction_message,
    map_overlay_glyph,
    map_selection_preview,
    panel_action,
    turn_dock_panel,
)
from hexengine.hooks.internal.ui_wire import (
    inform_popup_to_wire,
    interaction_messages_to_wire,
    map_overlays_to_wire,
    map_selection_preview_to_wire,
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
        css_class="hexdemo-turn-dock hexdemo-turn-dock--attack_ready",
    )
    wire = panel.to_wire_dict()
    assert wire["schema"] == 1
    assert wire["presentation_id"] == "attack_ready"
    assert wire["host"] == "user-controls"
    assert wire["actions"][0]["id"] == "end_phase"


def test_turn_action_dock_to_wire_rejects_dict_rows() -> None:
    legacy = {"schema": 1, "id": "legacy", "host": "user-controls", "actions": []}
    try:
        turn_action_dock_to_wire([legacy])
    except TypeError as exc:
        assert "TurnDockPanel" in str(exc)
    else:
        raise AssertionError("expected TypeError")


def test_inform_popup_to_wire_rejects_dict() -> None:
    try:
        inform_popup_to_wire({"text": "x", "kind": "info", "ttl_ms": 100})
    except TypeError as exc:
        assert "InformPopup" in str(exc)
    else:
        raise AssertionError("expected TypeError")


def test_inform_popup_dto_round_trip() -> None:
    dto = inform_popup(text="hello", ttl_ms=750)
    assert inform_popup_to_wire(dto)["ttl_ms"] == 750


def test_interaction_messages_to_wire_rejects_dict_rows() -> None:
    try:
        interaction_messages_to_wire(
            [{"schema": 1, "kind": "phase", "text": "x"}]
        )
    except TypeError as exc:
        assert "InteractionMessage" in str(exc)
    else:
        raise AssertionError("expected TypeError")


def test_interaction_messages_dto_round_trip() -> None:
    dto = interaction_message(
        kind="retreat",
        text="Retreat now",
        dedupe_key="combat_prompt",
        css_class="interaction-msg--retreat",
    )
    wire = interaction_messages_to_wire([dto])
    assert wire[0]["kind"] == "retreat"
    assert wire[0]["dedupe_key"] == "combat_prompt"


def test_map_overlays_to_wire_rejects_dict_rows() -> None:
    try:
        map_overlays_to_wire(
            [
                {
                    "schema": 1,
                    "id": "t1",
                    "kind": "glyph",
                    "hex": {"i": 0, "j": 0, "k": 0},
                    "text": "x",
                }
            ]
        )
    except TypeError as exc:
        assert "MapOverlay" in str(exc)
    else:
        raise AssertionError("expected TypeError")


def test_map_overlay_glyph_dto_round_trip() -> None:
    dto = map_overlay_glyph(
        id="combat-target-1",
        hex={"i": 1, "j": -1, "k": 0},
        text="🟎",
        css_class="hexdemo-combat-glyph-overlay",
    )
    wire = map_overlays_to_wire([dto])[0]
    assert wire["id"] == "combat-target-1"
    assert wire["hex"] == {"i": 1, "j": -1, "k": 0}
    assert wire["css_class"] == "hexdemo-combat-glyph-overlay"


def test_map_selection_preview_to_wire_rejects_dict() -> None:
    try:
        map_selection_preview_to_wire(
            {
                "kind": "attack_plan",
                "status_text": "x",
                "confirm_enabled": False,
            }
        )
    except TypeError as exc:
        assert "MapSelectionPreview" in str(exc)
    else:
        raise AssertionError("expected TypeError")


def test_map_selection_preview_dto_round_trip() -> None:
    dto = map_selection_preview(
        kind="attack_plan",
        status_text="Pick a target",
        confirm_enabled=False,
        panel_actions=(
            panel_action(
                id="attack_plan_cancel",
                action_type="AttackPlanCancel",
                label="Cancel",
                enabled=True,
            ),
        ),
        disable_end_phase=True,
        draft_presentation_id="attack_draft",
    )
    wire = map_selection_preview_to_wire(dto)
    assert wire["kind"] == "attack_plan"
    assert wire["panel_actions"][0]["id"] == "attack_plan_cancel"
    assert wire["disable_end_phase"] is True
    assert wire["draft_presentation_id"] == "attack_draft"


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
        current_segment={
            "schema": 1,
            "kind": "combat",
            "presentation_id": "attack_ready",
            "allowed_actions": ["Attack", "NextPhase"],
        },
    )
    panels = turn_action_dock_for_viewer(ctx)
    assert len(panels) == 1
    assert isinstance(panels[0], TurnDockPanel)
    wire = turn_action_dock_to_wire(panels)[0]
    assert wire["id"] == "turn_actions"
    assert wire.get("presentation_id") == "attack_ready"
