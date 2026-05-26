"""Engine default interaction panels for ``UIHook.INTERACTION_PANELS_FOR_VIEWER``."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..state import GameState


@dataclass(frozen=True, slots=True)
class InteractionPanelsContext:
    """Inputs for building per-viewer ``StateUpdate.interaction_panels`` rows."""

    state: GameState
    viewer_faction: str | None
    extension_key: str | None
    shell_ui: Mapping[str, Any]
    primary_actions: tuple[dict[str, Any], ...]


def default_interaction_panels_for_viewer(
    ctx: InteractionPanelsContext,
) -> list[dict[str, Any]]:
    """
    Engine catalog default: one ``user-controls`` host panel when ``primary_actions`` is non-empty.

    Titles add decorative ``html`` via the hook; actions are always engine-wired buttons.
    """

    actions = [dict(a) for a in ctx.primary_actions if isinstance(a, dict)]
    if not actions:
        return []
    return [
        {
            "schema": 1,
            "id": "primary_actions",
            "host": "user-controls",
            "css_class": "hexengine-interaction-panel--primary-actions",
            "actions": actions,
            "inputs": [],
        }
    ]


__all__ = ["InteractionPanelsContext", "default_interaction_panels_for_viewer"]
