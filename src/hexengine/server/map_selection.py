"""Authoritative map-selection previews (draft validation + commit payload)."""

from __future__ import annotations

from typing import Any

from ..hooks.core import ENGINE_DEFAULT
from ..hooks.internal.ui_wire import map_selection_preview_to_wire
from ..hooks.map_selection_registry import resolve_map_selection_preview
from ..hooks.title import TitleHooks
from ..state import GameState
from ..ui.display import empty_map_selection_preview


def compute_map_selection_preview(
    *,
    state: GameState,
    player_faction: str,
    kind: str,
    draft: dict[str, Any],
    shell_ui: dict[str, Any],
    board_hexes: list,
    hooks: TitleHooks,
    markers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Return wire fields for ``MapSelectionPreviewWire`` (empty when unsupported).
    """
    k = str(kind or "").strip()
    raw = resolve_map_selection_preview(
        state=state,
        player_faction=player_faction,
        kind=k,
        draft=draft if isinstance(draft, dict) else {},
        shell_ui=shell_ui if isinstance(shell_ui, dict) else {},
        hooks=hooks,
        board_hexes=board_hexes,
        markers=markers,
    )
    if raw is ENGINE_DEFAULT:
        return map_selection_preview_to_wire(empty_map_selection_preview(k))
    return map_selection_preview_to_wire(raw)


__all__ = ["compute_map_selection_preview"]
