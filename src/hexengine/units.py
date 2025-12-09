from .hexes.types import Hex
from .map.layout import HexLayout
import js
import logging
from typing import TYPE_CHECKING, Iterable, Protocol


class GraphicsCreator(Protocol):
    def create_graphics(self, display_unit: "DisplayUnit"):
        ...

class GenericGraphicsCreator (GraphicsCreator):
    def create_graphics(self, display_unit: "DisplayUnit"):

        w = 2 * int(display_unit._hex_layout.size / 1.5)
        if w % 2 != 0:
            w += 1
        h = 2 * int(display_unit._hex_layout.size / 1.5)
        if h % 2 != 0:
            h += 1

        rect = js.document.createElementNS("http://www.w3.org/2000/svg", "rect")

        rect.setAttribute("x", -w // 2)
        rect.setAttribute("y", -h // 2)
        rect.setAttribute("width", w)
        rect.setAttribute("height", h)
        rect.setAttribute("rx", "4")
        rect.setAttribute("ry", "4")
        rect.setAttribute("data-unit", display_unit.unit_id)
        display_unit.proxy.appendChild(rect)

        # remember to set 'data unit' on all elements for event handling!

        c = js.document.createElementNS("http://www.w3.org/2000/svg", "circle")
        c.setAttribute("cx", "0")  
        c.setAttribute("cy", "-6")  
        c.setAttribute("r", str(min(w, h) // 5))
        c.setAttribute("class", "unit-center")
        c.setAttribute("data-unit", display_unit.unit_id)
        display_unit.proxy.appendChild(c)


        t = js.document.createElementNS("http://www.w3.org/2000/svg", "text")
        t.setAttribute("x", "0")
        t.setAttribute("y", "12")
        t.textContent = "2-4-8"
        t.setAttribute("class", "unit-label")
        t.setAttribute("data-unit", display_unit.unit_id)

        display_unit.proxy.appendChild(t)

class DisplayUnit:
    """The display component of a game unit."""

    def __init__(
        self, unit_id: str, unit_type: str, proxy: "js.Proxy",
        layout: HexLayout = None
    ):
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.proxy = proxy
        self._hex = Hex(-1, -1, 2)  # Default off-map
        self._hex_layout = layout

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

    def _get_active(self) -> bool:
        return self.proxy.classList.contains("active")

    def _set_active(self, value: bool):
        if value:
            self.proxy.classList.add("active")
        else:
            self.proxy.classList.remove("active")

    def __repr__(self):
        return (
            f"<Unit id={self.unit_id} hex=({self._hex.i},{self._hex.j},{self._hex.k})>"
        )

    visible = property(_get_visible, _set_visible)
    position = property(_get_position, _set_position)
    rotation = property(_get_rotation, _set_rotation)
    active = property(_get_active, _set_active)


class GameUnit:
    """A game unit with logic and state."""

    def __init__(self, unit_id: str, unit_type: str, unit_display: DisplayUnit):
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.display = unit_display
        self.health = 100  # Default health

    def move_to(self, hex: Hex):
        self.display.position = hex


    def _set_visible(self, value: bool):
        self.display.visible = value

    def _get_visible(self) -> bool:
        return self.display.visible

    def _set_position(self, hex: Hex):
        self.display.position = hex

    def _get_position(self) -> Hex:
        return self.display.position    

    def _get_rotation(self) -> float:
        return self.display.rotation
    
    def _set_rotation(self, angle: float):
        self.display.rotation = angle
    
    def _get_active(self) -> bool:
        return self.display.active  

    def _set_active(self, value: bool):
        self.display.active = value
    

    visible = property(_get_visible, _set_visible)
    position = property(_get_position, _set_position)
    rotation = property(_get_rotation, _set_rotation)
    active = property(_get_active, _set_active)


    def __repr__(self):
        return f"<GameUnit id={self.unit_id} type={self.unit_type} at=({self.display.position.i},{self.display.position.j},{self.display.position.k})>"

    def __hash__(self):
        return hash(hash(self.unit_id) ^ hash(self.unit_type))