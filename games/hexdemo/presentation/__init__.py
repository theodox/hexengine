"""Hexdemo presentation helpers (dock, inform, and interaction banner copy)."""

from .dock import dock_headline, dock_panel_html
from .inform import inform_popup_for_profile
from .interaction_messages import (
    advance_gate_banners_for_viewer,
    combat_instruction_for_viewer,
)

__all__ = [
    "advance_gate_banners_for_viewer",
    "combat_instruction_for_viewer",
    "dock_headline",
    "dock_panel_html",
    "inform_popup_for_profile",
]
