"""
Author-facing presentation builders (re-export ``hexengine.ui.display``).

Titles import from here for dock panels, popups, banner rows, map overlays, and segment
enrich patches. Combat cleanup gate dock rows live in ``authoring.patterns.combat``
(``combat_gate_panel_actions``). The engine converts these dataclasses to wire dicts in
``hexengine.hooks.internal.ui_wire`` — pack code should not assemble wire ``schema``
fields or raw banner dicts by hand.

Runtime server modules must not import this module; use ``hexengine.ui.display`` types
from ``ui_wire`` only.
"""

from __future__ import annotations

from ..hooks.ui_segment import (
    SegmentPresentationPatch,
    segment_presentation_patch,
)
from ..ui.display import (
    InformPopup,
    InteractionMessage,
    MapOverlay,
    MapSelectionPreview,
    PanelAction,
    TurnDockPanel,
    empty_map_selection_preview,
    inform_popup,
    interaction_message,
    map_overlay_glyph,
    map_selection_preview,
    panel_action,
    turn_dock_panel,
)

__all__ = [
    "InformPopup",
    "InteractionMessage",
    "MapOverlay",
    "MapSelectionPreview",
    "PanelAction",
    "SegmentPresentationPatch",
    "TurnDockPanel",
    "empty_map_selection_preview",
    "inform_popup",
    "interaction_message",
    "map_overlay_glyph",
    "map_selection_preview",
    "panel_action",
    "segment_presentation_patch",
    "turn_dock_panel",
]
