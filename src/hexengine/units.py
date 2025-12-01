from .hexes.types import Hex
from .map.layout import HexLayout
import js
import logging
from typing import TYPE_CHECKING, Iterable

class Unit:
    """The display component of a game unit."""

    def __init__(self, unit_id: str, unit_type: str, proxy: "JSProxys", layout: HexLayout = None):
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.proxy = proxy
        self._hex = Hex(-1,-1,2)  # Default off-map
        self._hex_layout = layout
        self._create_graphics()

    def _set_visible(self, value: bool):
        if value:
            self.proxy.setAttribute("display", "block")
        else:
            self.proxy.setAttribute("display", "none")

    def _get_visible(self) -> bool:
        return self.proxy.getAttribute("display") != "none"

    def _set_position(self, hex: Hex):
        self._hex = hex
        x, y = self._hex_layout.hex_to_pixel(self._hex)
        logging.getLogger("unit").debug(f"Setting unit {self.unit_id} position to hex ({self._hex.i},{hex.j},{hex.k}) -> pixel ({x},{y})")
        self.proxy.setAttribute("transform", f"translate({x},{y})")

    def _get_position(self) -> Hex:
        return self._hex
    
    def _get_rotation(self) -> float:
        transform = self.proxy.getAttribute("transform")
        if "rotate(" in transform:
            start = transform.index("rotate(") + len("rotate(")
            end = transform.index(")", start)
            angle_str = transform[start:end]
            return float(angle_str)
        return 0.0
    
    def _set_rotation(self, angle: float):
        transform = self.proxy.getAttribute("transform")
        # Remove existing rotation if any
        if "rotate(" in transform:
            start = transform.index("rotate(")
            end = transform.index(")", start) + 1
            transform = transform[:start] + transform[end:]
        # Append new rotation
        transform += f" rotate({angle})"
        self.proxy.setAttribute("transform", transform)



    def __repr__(self):
        return f"<Unit id={self.unit_id} hex=({self._hex.i},{self._hex.j},{self._hex.k})>"
    
    def __hash__(self):
        return hash(self.unit_id)
    

    def _create_graphics(self):

        # tbd - this should be delegated to a sprite manager
        rect = js.document.createElementNS("http://www.w3.org/2000/svg", "rect")
        w = 2 * int(self._hex_layout.size / 1.5)
        if w % 2 != 0:
            w += 1
        h = 2 * int(self._hex_layout.size / 1.5)
        if h % 2 != 0:
            h += 1  


        rect.setAttribute("x", -w // 2)
        rect.setAttribute("y", -h // 2)
        rect.setAttribute("width", w)
        rect.setAttribute("height", h)
        rect.setAttribute("rx", "4")
        rect.setAttribute("ry", "4")
        rect.setAttribute("class", self.unit_type)
        self.proxy.appendChild(rect)
    



    
    visible = property(_get_visible, _set_visible)
    position = property(_get_position, _set_position)
    rotation = property(_get_rotation, _set_rotation)

class GameUnit:
    """A game unit with logic and state."""

    def __init__(self, unit_id: str, unit_type: str, unit_display: Unit):
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.display = unit_display
        self.health = 100  # Default health

    def move_to(self, hex: Hex):
        self.display.position = hex

    def set_visible(self, visible: bool):
        self.display.visible = visible

    def __repr__(self):
        return f"<GameUnit id={self.unit_id} type={self.unit_type} at=({self.display.position.i},{self.display.position.j},{self.display.position.k})>"