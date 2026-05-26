"""Panel action dispatch registry."""

from __future__ import annotations

from hexengine.game.arcs.client_panel_actions import resolve_panel_action_route


def test_resolve_attack_plan_cancel_local() -> None:
    route = resolve_panel_action_route(
        {"id": "attack_plan_cancel", "action_type": "AttackPlanCancel"}
    )
    assert route is not None
    assert route.mode == "local"
    assert route.method == "cancel_attack_plan"


def test_resolve_attack_preview_commit() -> None:
    route = resolve_panel_action_route(
        {"id": "attack_plan_confirm", "action_type": "Attack", "payload": {}}
    )
    assert route is not None
    assert route.mode == "preview_commit"
    assert route.wire_action_type == "Attack"
    assert route.after_method == "cancel_attack_plan"


def test_resolve_retreat_path_confirm_by_id() -> None:
    route = resolve_panel_action_route(
        {"id": "retreat_path_confirm", "action_type": "MoveUnit", "payload": {}}
    )
    assert route is not None
    assert route.mode == "local"
    assert route.method == "confirm_retreat_path"


def test_resolve_place_marker_confirm_by_id() -> None:
    route = resolve_panel_action_route(
        {"id": "place_marker_confirm", "action_type": "MoveMarker", "payload": {}}
    )
    assert route is not None
    assert route.mode == "local"
    assert route.method == "confirm_place_marker"


def test_resolve_place_marker_cancel_local() -> None:
    route = resolve_panel_action_route(
        {"id": "place_marker_cancel", "action_type": "PlaceMarkerCancel"}
    )
    assert route is not None
    assert route.method == "cancel_place_marker"


def test_resolve_next_phase_falls_through() -> None:
    assert (
        resolve_panel_action_route(
            {"id": "end_phase", "action_type": "NextPhase", "payload": {}}
        )
        is None
    )


def test_retreat_path_confirm_id_takes_precedence_over_move_unit_type() -> None:
    """``retreat_path_confirm`` is local even though wire ``action_type`` is MoveUnit."""
    route = resolve_panel_action_route(
        {"id": "retreat_path_confirm", "action_type": "MoveUnit"}
    )
    assert route is not None
    assert route.method == "confirm_retreat_path"
