import js  # pyright: ignore[reportMissingImports]
from typing import Iterable
from .layout import HexLayout
from ..units import Unit


class UnitLayer:
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


    def create_unit(self, unit_id: str, unit_type: str):
        if unit_id in self.units:
            raise ValueError(f"Unit with id {unit_id} already exists")
            
        # Create new proxy for unit type
        proxy = js.document.createElementNS("http://www.w3.org/2000/svg", "g")
        proxy.setAttribute("id", unit_id)
        proxy.setAttribute("data-unit-type", unit_type)
        proxy.setAttribute("display", "none")  # Initially hidden
        proxy.setAttribute("class", unit_type)  # Initial position
        self._svg.appendChild(proxy)
        new_unit = Unit(unit_id, unit_type, proxy, self._hex_layout)
        self.units[unit_id] = new_unit
        return new_unit

    def remove_unit(self, unit: Unit):
        if unit.unit_id not in self.units:
            raise ValueError(f"Unit with id {unit.unit_id} does not exist")
        unit.proxy.remove()
        del self.units[unit.unit_id]
        
    def get_unit(self, unit_id: str) -> Unit:
        if unit_id not in self.units:
            raise ValueError(f"Unit with id {unit_id} does not exist")
        return self.units[unit_id]
    
    def get_units(self) -> Iterable[Unit]:
        return self.units.values()
