"""Client SEQUENCE skin helpers for the turn action dock."""

from __future__ import annotations

from hexengine.game.arcs.client_interaction_panels import (
    effective_turn_dock_arc,
    replace_dock_arc_css_class,
    turn_dock_sequence_headline,
)


def test_effective_turn_dock_arc_prefers_draft_steps() -> None:
    assert effective_turn_dock_arc(
        "attack_ready",
        attack_draft=True,
        retreat_path_draft=False,
        place_marker_draft=False,
    ) == "attack_draft"
    assert effective_turn_dock_arc(
        "retreat_gate",
        attack_draft=False,
        retreat_path_draft=True,
        place_marker_draft=False,
    ) == "retreat_path_draft"
    assert effective_turn_dock_arc(
        "routine",
        attack_draft=False,
        retreat_path_draft=False,
        place_marker_draft=True,
    ) == "place_marker_draft"
    assert effective_turn_dock_arc(
        "routine",
        attack_draft=False,
        retreat_path_draft=False,
        place_marker_draft=False,
    ) == "routine"


def test_replace_dock_arc_css_class_swaps_modifier() -> None:
    css = "hexdemo-turn-dock hexdemo-turn-dock--attack_ready"
    assert (
        replace_dock_arc_css_class(css, "attack_draft")
        == "hexdemo-turn-dock hexdemo-turn-dock--attack_draft"
    )


def test_turn_dock_sequence_headline_attack_ready_idle() -> None:
    hl = turn_dock_sequence_headline(
        server_headline="Combat",
        server_arc="attack_ready",
        preview_status="",
        attack_draft=False,
        retreat_path_draft=False,
        place_marker_draft=False,
        attack_ready_idle=True,
        attack_pick_target_status="Pick a target.",
        attack_target_set_status="Target set.",
    )
    assert hl == "Pick a target."


def test_turn_dock_sequence_headline_attack_draft_uses_preview() -> None:
    hl = turn_dock_sequence_headline(
        server_headline="Combat",
        server_arc="attack_ready",
        preview_status="Confirm when ready.",
        attack_draft=True,
        retreat_path_draft=False,
        place_marker_draft=False,
        attack_ready_idle=False,
        attack_pick_target_status="Pick a target.",
        attack_target_set_status="Target set.",
    )
    assert hl == "Confirm when ready."


def test_turn_dock_sequence_headline_retreat_path_draft() -> None:
    hl = turn_dock_sequence_headline(
        server_headline="Retreat",
        server_arc="retreat_gate",
        preview_status="Retreat path complete — confirm or undo.",
        attack_draft=False,
        retreat_path_draft=True,
        place_marker_draft=False,
        attack_ready_idle=False,
        attack_pick_target_status="",
        attack_target_set_status="",
    )
    assert hl == "Retreat path complete — confirm or undo."
