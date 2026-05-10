"""
UI-related hooks.

Role in turn resolution:

- The server remains authoritative and computes per-recipient `StateUpdate` payloads.
- Titles can customize what transient messages are shown to each viewer by returning
  `interaction_messages` for a given authoritative `GameState`.
- The browser client renders these messages using CSS (titles can provide CSS via
  `turn_rules.faction_ui.css`).
- Optional `map_overlays` returns a list of overlay specs; the engine client creates
  and removes DOM under `#map-world` (map-space coordinates, same pan/zoom as units).

Engine-level messages (network disconnect, exceptions, etc.) are always allowed to
override UI locally on the client and do not require title hooks.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

from ..state import GameState
from .core import DEFAULT


@dataclass(frozen=True, slots=True)
class UIHooks:
    """
    UI policy surface consulted by the server when building per-recipient `StateUpdate`.

    - Return `DEFAULT` to request engine defaults.
    - Return a list of message dicts to fully control transient per-viewer banners.
    """

    interaction_messages: (
        Callable[[GameState, str | None], list[dict[str, Any]] | object] | None
    ) = None

    popup_message: (
        Callable[[GameState, str | None, str, str], dict[str, Any] | object] | None
    ) = None

    map_overlays: (
        Callable[[GameState, str | None], list[dict[str, Any]] | object] | None
    ) = None

    def messages(self, state: GameState, viewer_faction: str | None) -> list[dict[str, Any]] | object:
        if self.interaction_messages is None:
            return DEFAULT
        return self.interaction_messages(state, viewer_faction)

    def popup(
        self,
        state: GameState,
        viewer_faction: str | None,
        target_kind: str,
        target_id: str,
    ) -> dict[str, Any] | object:
        if self.popup_message is None:
            return DEFAULT
        return self.popup_message(state, viewer_faction, target_kind, target_id)

    def overlays(self, state: GameState, viewer_faction: str | None) -> list[dict[str, Any]] | object:
        if self.map_overlays is None:
            return DEFAULT
        return self.map_overlays(state, viewer_faction)


__all__ = ["UIHooks"]

