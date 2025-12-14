from ..hexes.types import Hex
from ..map.layout import HexLayout
import js
from typing import TYPE_CHECKING, Iterable, Protocol

# Display constants
UNIT_SIZE_DIVISOR = 1.5
HEAD_OFFSET_DIVISOR = 5
HEAD_RADIUS_DIVISOR = 5


class GraphicsCreator(Protocol):
    BASE_CLASSES = ("unit",)

    def create(self, display_unit: "DisplayUnit"): ...

    def _get_unit_size(self, display_unit):
        w = 2 * int(display_unit._hex_layout.size / UNIT_SIZE_DIVISOR)
        if w % 2 != 0:
            w += 1
        h = 2 * int(display_unit._hex_layout.size / UNIT_SIZE_DIVISOR)
        if h % 2 != 0:
            h += 1
        return w, h

    def _attach(self, display_unit, element, *classes):
        element.setAttribute("data-unit", display_unit.unit_id)
        for cl in classes:
            element.classList.add(cl)
        display_unit.proxy.appendChild(element)


class GenericGraphicsCreator(GraphicsCreator):
    BASE_CLASSES = ("soldier", "unit")

    def create(self, display_unit: "DisplayUnit"):
        display_unit.push_classes(*self.BASE_CLASSES)
        w, h = self._get_unit_size(display_unit)

        rect = js.document.createElementNS("http://www.w3.org/2000/svg", "rect")
        rect.setAttribute("x", -w // 2)
        rect.setAttribute("y", -h // 2)
        rect.setAttribute("width", w - 2)
        rect.setAttribute("height", h - 2)
        self._attach(display_unit, rect)

        c = js.document.createElementNS("http://www.w3.org/2000/svg", "circle")
        c.setAttribute("cx", "0")
        c.setAttribute("cy", -h // HEAD_OFFSET_DIVISOR)
        c.setAttribute("r", str(min(w, h) // HEAD_RADIUS_DIVISOR))
        self._attach(display_unit, c, "soldier-center")

        t = js.document.createElementNS("http://www.w3.org/2000/svg", "text")
        t.setAttribute("x", "0")
        t.setAttribute("y", h // 3)
        self._attach(display_unit, t)
        display_unit.set_text_element(t)
        return display_unit


class CanuckGraphicsCreator(GraphicsCreator):
    BASE_CLASSES = ("unit", "canuck")

    def create(self, display_unit: "DisplayUnit"):
        # Implement specific graphics creation for Canuck units
        display_unit.push_classes(*self.BASE_CLASSES)
        w, h = self._get_unit_size(display_unit)

        rect = js.document.createElementNS("http://www.w3.org/2000/svg", "rect")
        rect.setAttribute("x", -w // 2)
        rect.setAttribute("y", -h // 2)
        rect.setAttribute("width", w)
        rect.setAttribute("height", h)
        rect.setAttribute("fill", "lightblue")
        self._attach(display_unit, rect)

        flag = js.document.createElementNS("http://www.w3.org/2000/svg", "image")
        flag.setAttribute("x", -w // 2)
        flag.setAttribute("y", -h // 2)
        flag.setAttribute("width", w)
        flag.setAttribute("height", h)
        flag.setAttributeNS(
            "http://www.w3.org/1999/xlink", "href", "resources/canada.png"
        )
        self._attach(display_unit, flag)
        return display_unit


class DisplayUnit:
    """The display component of a game unit."""

    def __init__(
        self, unit_id: str, unit_type: str, proxy: "js.Proxy", layout: HexLayout = None
    ):
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.proxy = proxy
        self._hex = Hex(-2, -2, 4)  # Default off-map
        self._hex_layout = layout
        self.text_element = None

    def push_classes(self, *classes: Iterable[str]):
        for cl in classes:
            self.proxy.classList.add(cl)

    def set_text_element(self, element: "js.Element"):
        self.text_element = element

    def set_text(self, text: str):
        if self.text_element:
            self.text_element.textContent = text

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
