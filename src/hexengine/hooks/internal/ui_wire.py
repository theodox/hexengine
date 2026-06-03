"""
Convert title UI hook results to wire dicts (single engine adapter).

Title hooks may return presentation dataclasses from ``hexengine.ui.display`` or
legacy ``dict`` rows; this module is the only place that should know both shapes.
"""

from __future__ import annotations

from typing import Any

from ...ui.display import InformPopup, InteractionPanel, TurnDockPanel


def turn_action_dock_to_wire(raw: object) -> list[dict[str, Any]]:
    """Normalize ``TURN_ACTION_DOCK_FOR_VIEWER`` hook output to wire panel dicts."""

    if not isinstance(raw, list):
        raise TypeError(
            "turn_action_dock_for_viewer must return list, "
            f"got {type(raw).__name__}"
        )
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, TurnDockPanel):
            out.append(item.to_wire_dict())
        elif isinstance(item, InteractionPanel):
            out.append(item.to_wire_dict())
        elif isinstance(item, dict):
            out.append(dict(item))
        else:
            raise TypeError(
                "turn_action_dock_for_viewer items must be TurnDockPanel, "
                f"InteractionPanel, or dict, got {type(item).__name__}"
            )
    return out


def inform_popup_to_wire(raw: object) -> dict[str, Any]:
    """Normalize ``INFORM_POPUP`` / ``inform_popup`` hook output to a wire popup dict."""

    if isinstance(raw, InformPopup):
        return raw.to_wire_dict()
    if isinstance(raw, dict):
        return dict(raw)
    raise TypeError(
        f"inform_popup hook must return InformPopup or dict, got {type(raw).__name__}"
    )


__all__ = ["inform_popup_to_wire", "turn_action_dock_to_wire"]
