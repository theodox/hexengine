"""
Turn action dock button dispatch (local handlers + preview commit ratify).

Titles declare routes in ``game_data.toml`` → ``[client_contract.panel_action_routes]``;
the server mirrors them on ``turn_rules.client_contract``. When a title omits routes,
the engine falls back to built-in reference routes for common map-selection flows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

PanelActionMode = Literal["local", "preview_commit"]


@dataclass(frozen=True, slots=True)
class PanelActionRoute:
    mode: PanelActionMode
    method: str | None = None
    wire_action_type: str | None = None
    after_method: str | None = None
    match_action_type: str | None = None
    match_id: str | None = None


def _spec_action_type(spec: dict[str, Any]) -> str:
    return str(spec.get("action_type", "")).strip()


def _spec_id(spec: dict[str, Any]) -> str:
    return str(spec.get("id", "")).strip()


def _route_matches(spec: dict[str, Any], route: PanelActionRoute) -> bool:
    if route.match_id is not None and _spec_id(spec) == route.match_id:
        return True
    if (
        route.match_action_type is not None
        and _spec_action_type(spec) == route.match_action_type
    ):
        if route.match_id is None:
            return True
        return _spec_id(spec) == route.match_id
    return False


DEFAULT_PANEL_ACTION_ROUTES: tuple[PanelActionRoute, ...] = (
    PanelActionRoute(
        mode="local",
        match_action_type="AttackPlanCancel",
        method="cancel_attack_plan",
    ),
    PanelActionRoute(
        mode="local",
        match_action_type="RetreatPathCancel",
        method="cancel_retreat_path",
    ),
    PanelActionRoute(
        mode="local",
        match_action_type="RetreatPathUndo",
        method="undo_retreat_path_hex",
    ),
    PanelActionRoute(
        mode="local",
        match_id="retreat_path_confirm",
        method="confirm_retreat_path",
    ),
    PanelActionRoute(
        mode="local",
        match_action_type="PlaceMarkerCancel",
        method="cancel_place_marker",
    ),
    PanelActionRoute(
        mode="local",
        match_id="place_marker_confirm",
        method="confirm_place_marker",
    ),
    PanelActionRoute(
        mode="preview_commit",
        match_action_type="Attack",
        wire_action_type="Attack",
        after_method="cancel_attack_plan",
    ),
)

# Back-compat alias for tests and docs that reference the old name.
PANEL_ACTION_ROUTES = DEFAULT_PANEL_ACTION_ROUTES


def _manifest_routes(game: Any | None) -> tuple[PanelActionRoute, ...] | None:
    if game is None:
        return None
    td_fn = getattr(game, "_client_title_data", None)
    if not callable(td_fn):
        return None
    rows = td_fn().client_contract.panel_action_routes
    if not rows:
        return None
    return tuple(
        PanelActionRoute(
            mode=row.mode,
            method=row.method,
            wire_action_type=row.wire_action_type,
            after_method=row.after_method,
            match_action_type=row.match_action_type,
            match_id=row.match_id,
        )
        for row in rows
    )


def panel_action_routes_for_game(game: Any | None = None) -> tuple[PanelActionRoute, ...]:
    """Title manifest when present, else engine defaults."""
    manifest = _manifest_routes(game)
    if manifest is not None:
        return manifest
    return DEFAULT_PANEL_ACTION_ROUTES


def resolve_panel_action_route(
    spec: dict[str, Any],
    game: Any | None = None,
    *,
    routes: tuple[PanelActionRoute, ...] | None = None,
) -> PanelActionRoute | None:
    rows = routes if routes is not None else panel_action_routes_for_game(game)
    for route in rows:
        if _route_matches(spec, route):
            return route
    return None


def dispatch_panel_action_route(
    game: Any,
    spec: dict[str, Any],
    route: PanelActionRoute,
) -> bool:
    """
    Run a registered panel action route.

    Returns True when the click was fully handled (no default RPC).
    """
    if route.mode == "local":
        method = route.method
        if not method:
            return False
        fn = getattr(game, method, None)
        if not callable(fn):
            return False
        fn()
        return True

    if route.mode == "preview_commit":
        prev = getattr(game, "_map_selection_preview", None)
        if not isinstance(prev, dict) or not prev.get("confirm_enabled"):
            return False
        commit = prev.get("commit_payload")
        if not isinstance(commit, dict) or not commit:
            return False
        wire = str(route.wire_action_type or _spec_action_type(spec) or "").strip()
        if not wire:
            return False
        game.execute_action_request(wire, dict(commit))  # type: ignore[attr-defined]
        after = route.after_method
        if after:
            fn = getattr(game, after, None)
            if callable(fn):
                fn()
        return True

    return False


__all__ = [
    "DEFAULT_PANEL_ACTION_ROUTES",
    "PANEL_ACTION_ROUTES",
    "PanelActionRoute",
    "dispatch_panel_action_route",
    "panel_action_routes_for_game",
    "resolve_panel_action_route",
]
