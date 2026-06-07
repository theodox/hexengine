"""
Convert title UI hook results to wire dicts (single engine adapter).

Title hooks return presentation dataclasses from ``hexengine.ui.display``; this
module is the only place that serializes them for ``StateUpdate`` / ``ui_popup``.
"""

from __future__ import annotations

from typing import Any

from ...ui.display import InformPopup, InteractionPanel, TurnDockPanel


def turn_action_dock_to_wire(raw: object) -> list[dict[str, Any]]:
    """Normalize ``TURN_ACTION_DOCK_FOR_VIEWER`` hook output to wire panel dicts."""

    if not isinstance(raw, list):
        raise TypeError(
            f"turn_action_dock_for_viewer must return list, got {type(raw).__name__}"
        )
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, TurnDockPanel):
            out.append(item.to_wire_dict())
        elif isinstance(item, InteractionPanel):
            out.append(item.to_wire_dict())
        else:
            raise TypeError(
                "turn_action_dock_for_viewer items must be TurnDockPanel or "
                f"InteractionPanel, got {type(item).__name__}"
            )
    return out


def inform_popup_to_wire(raw: object) -> dict[str, Any]:
    """Normalize ``INFORM_POPUP`` / ``inform_popup`` hook output to a wire popup dict."""

    if not isinstance(raw, InformPopup):
        raise TypeError(
            f"inform_popup hook must return InformPopup, got {type(raw).__name__}"
        )
    return raw.to_wire_dict()


__all__ = ["inform_popup_to_wire", "turn_action_dock_to_wire"]
