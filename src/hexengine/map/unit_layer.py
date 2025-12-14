import logging
import js  # pyright: ignore[reportMissingImports]
from typing import Iterable
from .layout import HexLayout
from ..units import DisplayUnit, GameUnit


class UnitLayer:
    """
    This is the display layer for game units on the map.
    It manages the creation, updating, and removal of unit graphics."""

    def __init__(
        self,
        svg_element: js.SVGElement,
        hex_layout: HexLayout,
        hex_color: str,
        hex_stroke: int,
    ):
        self._svg = svg_element
        self._hex_layout = hex_layout
        self._hex_color = hex_color
        self._hex_stroke = hex_stroke
        self.units = {}

    def get_display_unit(self, unit_id: str, unit_type: str) -> DisplayUnit:
        # Create new proxy for unit type
        proxy = js.document.createElementNS("http://www.w3.org/2000/svg", "g")
        proxy.setAttribute("id", unit_id)
        proxy.setAttribute("data-unit-type", unit_type)
        proxy.setAttribute("display", "none")
        proxy.setAttribute("user-select", "none")
        self._svg.appendChild(proxy)
        return DisplayUnit(unit_id, unit_type, proxy, self._hex_layout)

    def add_unit(self, unit: GameUnit):
        if unit.unit_id in self.units:
            raise ValueError(f"Unit with id {unit.unit_id} already exists")
        else:
            logger = logging.getLogger("game_logger")
            logger.info(f"Adding unit {unit.unit_id} of type {unit.unit_type}")
            logger.info(f"display {unit.display}")

        self.units[unit.unit_id] = unit

    def remove_unit(self, unit: DisplayUnit):
        if unit.unit_id not in self.units:
            raise ValueError(f"Unit with id {unit.unit_id} does not exist")
        unit.proxy.remove()
        del self.units[unit.unit_id]

    def get_unit(self, unit_id: str) -> DisplayUnit:
        if unit_id not in self.units:
            raise ValueError(f"Unit with id {unit_id} does not exist")
        return self.units[unit_id]

    def unit_by_position(self) -> Iterable[DisplayUnit]:
        return {u.position: u for u in self.units.values()}
