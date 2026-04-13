"""
Optional marker placement factories (see `hexengine.state.marker_placement`).
"""

from __future__ import annotations

from hexengine.state.marker_placement import MarkerPlacementRule


def default_marker_placement_rule() -> MarkerPlacementRule | None:
    """
    Return `None` to use the engine default (board hex, no active unit).

    Replace with a custom `MarkerPlacementRule` callable when hexdemo defines placement.
    """
    return None
