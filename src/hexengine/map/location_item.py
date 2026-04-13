"""Plain data for building a `hexengine.map.location.Location` (no display / `hexengine.game.game.Game` in the ctor)."""

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
        hex_color: str | None = None,
    ) -> None:
        self.position: Hex = pos
        self.movement_cost = movement_cost
        self.type = loc_type
        self.assault_modifier = assault_modifier
        self.ranged_modifier = ranged_modifier
        self.block_los = block_los
        self.hex_color = hex_color
