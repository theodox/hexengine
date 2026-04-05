"""
Data type for scenario location definitions.

Lives in map so that map.location can use it without importing from scenarios.base,
breaking the circular dependency: map.location <-> scenarios.base.
"""

from __future__ import annotations

from ..hexes.types import Hex


class LocationItem:
    """Definition of a terrain location for use in scenarios (no display/Game dependency)."""

    def __init__(
        self,
        pos: Hex,
        loc_type: str,
        movement_cost: float,
        assault_modifier: float,
        ranged_modifier: float,
        block_los: bool,
    ) -> None:
        self.position: Hex = pos
        self.movement_cost = movement_cost
        self.type = loc_type
        self.assault_modifier = assault_modifier
        self.ranged_modifier = ranged_modifier
        self.block_los = block_los
