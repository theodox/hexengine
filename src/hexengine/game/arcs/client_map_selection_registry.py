"""
Client-side ``map_selection_preview`` apply handlers keyed by ``InteractionKind``.

New SELECT kinds register an apply method name here; mixins implement ``_apply_*``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ...gamedef.interactions import InteractionKind

PreviewApplyFn = Callable[[dict[str, Any]], None]

# (InteractionKind, apply method on Game)
_MAP_SELECTION_APPLY_METHODS: tuple[tuple[str, str], ...] = (
    (InteractionKind.ATTACK_PLAN, "_apply_attack_plan_preview"),
    (InteractionKind.RETREAT_PATH, "_apply_retreat_path_preview"),
    (InteractionKind.PLACE_MARKER, "_apply_place_marker_preview"),
)


def map_selection_preview_handlers(game: Any) -> dict[str, PreviewApplyFn]:
    """Bound preview apply handlers for kinds implemented on ``game``."""
    out: dict[str, PreviewApplyFn] = {}
    for kind, method_name in _MAP_SELECTION_APPLY_METHODS:
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
