"""
Client-side ``map_selection_preview`` apply handlers keyed by ``InteractionKind``.

Titles declare rows in ``game_data.toml`` → ``[client_contract.select_modes]``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ...gamedef.interactions import InteractionKind

PreviewApplyFn = Callable[[dict[str, Any]], None]

_DEFAULT_MAP_SELECTION_APPLY_METHODS: tuple[tuple[str, str], ...] = (
    (InteractionKind.ATTACK_PLAN, "_apply_attack_plan_preview"),
    (InteractionKind.RETREAT_PATH, "_apply_retreat_path_preview"),
    (InteractionKind.PLACE_MARKER, "_apply_place_marker_preview"),
)


def _apply_rows_for_game(game: Any) -> tuple[tuple[str, str], ...]:
    td_fn = getattr(game, "_client_title_data", None)
    if callable(td_fn):
        rows = td_fn().client_contract.select_modes
        if rows:
            return tuple((r.kind, r.apply_method) for r in rows)
    return _DEFAULT_MAP_SELECTION_APPLY_METHODS


def map_selection_preview_handlers(game: Any) -> dict[str, PreviewApplyFn]:
    """Bound preview apply handlers for kinds implemented on ``game``."""
    out: dict[str, PreviewApplyFn] = {}
    for kind, method_name in _apply_rows_for_game(game):
        fn = getattr(game, method_name, None)
        if callable(fn):
            out[str(kind)] = fn
    return out


def client_has_map_selection_kind(game: Any, kind: str) -> bool:
    return str(kind).strip() in map_selection_preview_handlers(game)


__all__ = [
    "map_selection_preview_handlers",
    "client_has_map_selection_kind",
]
