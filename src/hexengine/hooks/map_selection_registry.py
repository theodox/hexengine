"""
Registry of ``InteractionKind`` values to title preview hooks.

Titles bind hooks on existing bundles (e.g. ``AttackHook.ATTACK_PLAN_PREVIEW``).
The server dispatches ``map_selection_preview_request`` by ``kind`` through this table.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ..gamedef.interactions import InteractionKind
from .attack import AttackPlanPreviewContext
from .core import ENGINE_DEFAULT
from .movement import RetreatPathPreviewContext
from .title import TitleHooks
from ..ui.display import MapSelectionPreview
from .ui import PlaceMarkerPreviewContext

MapSelectionPreviewFn = Callable[..., MapSelectionPreview | object]
BoundCheckFn = Callable[[TitleHooks], bool]


def _ATTACK_PLAN_BOUND(h):
    return h.attack.attack_plan_preview is not None


def _RETREAT_PATH_BOUND(h):
    return h.movement.retreat_path_preview is not None


def _PLACE_MARKER_BOUND(h):
    return h.ui.place_marker_preview is not None


def _attack_plan_preview(
    *,
    state: Any,
    player_faction: str,
    draft: Mapping[str, Any],
    shell_ui: Mapping[str, Any],
    hooks: TitleHooks,
    board_hexes: list[Any] | None = None,
    **_kwargs: Any,
) -> MapSelectionPreview | object:
    fn = hooks.attack.attack_plan_preview
    if fn is None:
        return ENGINE_DEFAULT
    ctx = AttackPlanPreviewContext(
        state=state,
        player_faction=str(player_faction).strip(),
        draft=dict(draft),
        shell_ui=dict(shell_ui),
    )
    return fn(ctx)


def _retreat_path_preview(
    *,
    state: Any,
    player_faction: str,
    draft: Mapping[str, Any],
    shell_ui: Mapping[str, Any],
    hooks: TitleHooks,
    board_hexes: list[Any] | None = None,
    **_kwargs: Any,
) -> MapSelectionPreview | object:
    fn = hooks.movement.retreat_path_preview
    if fn is None:
        return ENGINE_DEFAULT
    ctx = RetreatPathPreviewContext(
        state=state,
        player_faction=str(player_faction).strip(),
        draft=dict(draft),
        shell_ui=dict(shell_ui),
    )
    return fn(ctx)


def _place_marker_preview(
    *,
    state: Any,
    player_faction: str,
    draft: Mapping[str, Any],
    shell_ui: Mapping[str, Any],
    hooks: TitleHooks,
    board_hexes: list[Any] | None = None,
    markers: list[Any] | None = None,
    **_kwargs: Any,
) -> MapSelectionPreview | object:
    fn = hooks.ui.place_marker_preview
    if fn is None:
        return ENGINE_DEFAULT
    rows = (
        [dict(m) for m in markers if isinstance(m, dict)]
        if isinstance(markers, list)
        else ()
    )
    ctx = PlaceMarkerPreviewContext(
        state=state,
        player_faction=str(player_faction).strip(),
        draft=dict(draft),
        shell_ui=dict(shell_ui),
        markers=tuple(rows),
    )
    return fn(ctx)


# Rows: kind, resolver, is hook bound for this title?
_MAP_SELECTION_ROWS: list[tuple[str, MapSelectionPreviewFn, BoundCheckFn]] = [
    (InteractionKind.ATTACK_PLAN, _attack_plan_preview, _ATTACK_PLAN_BOUND),
    (InteractionKind.RETREAT_PATH, _retreat_path_preview, _RETREAT_PATH_BOUND),
    (InteractionKind.PLACE_MARKER, _place_marker_preview, _PLACE_MARKER_BOUND),
]


def map_selection_kinds_in_registry() -> tuple[str, ...]:
    """Stable list of kinds the engine can route (title may omit the hook)."""

    return tuple(kind for kind, _, _ in _MAP_SELECTION_ROWS)


def bound_map_selection_kinds(hooks: TitleHooks) -> frozenset[str]:
    """Kinds with a title hook callable bound for this match."""

    return frozenset(
        kind for kind, _, is_bound in _MAP_SELECTION_ROWS if is_bound(hooks)
    )


def resolve_map_selection_preview(
    *,
    state: Any,
    player_faction: str,
    kind: str,
    draft: Mapping[str, Any],
    shell_ui: Mapping[str, Any],
    hooks: TitleHooks,
    board_hexes: list[Any] | None = None,
    markers: list[Any] | None = None,
) -> MapSelectionPreview | object:
    """Dispatch preview for ``kind``; return ``ENGINE_DEFAULT`` if kind is unknown."""

    k = str(kind or "").strip()
    for kind_id, resolver, _ in _MAP_SELECTION_ROWS:
        if kind_id != k:
            continue
        return resolver(
            state=state,
            player_faction=player_faction,
            draft=draft,
            shell_ui=shell_ui,
            hooks=hooks,
            board_hexes=board_hexes,
            markers=markers,
        )
    return ENGINE_DEFAULT


__all__ = [
    "bound_map_selection_kinds",
    "map_selection_kinds_in_registry",
    "resolve_map_selection_preview",
]
