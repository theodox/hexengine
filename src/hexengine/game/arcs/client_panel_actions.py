"""
Turn action dock button dispatch (local handlers + preview commit ratify).

Titles emit ``action_type`` / ``id`` on dock and preview ``panel_actions`` rows;
the client resolves them here before falling through to ``action_request``.
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


PANEL_ACTION_ROUTES: tuple[PanelActionRoute, ...] = (
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


def resolve_panel_action_route(spec: dict[str, Any]) -> PanelActionRoute | None:
    for route in PANEL_ACTION_ROUTES:
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
    "PANEL_ACTION_ROUTES",
    "PanelActionRoute",
    "dispatch_panel_action_route",
    "resolve_panel_action_route",
]
