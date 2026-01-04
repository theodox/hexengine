from contextlib import contextmanager
from typing import Iterable, Protocol

from ..document import js
from ..hexes.types import Hex
from ..map.layout import HexLayout


class GraphicsCreator(Protocol):
    BASE_CLASSES = ("unit",)
    STYLE_CREATED = False

    # Display constants
    UNIT_SIZE_DIVISOR = 1.5
    HEAD_OFFSET_DIVISOR = 5
    HEAD_RADIUS_DIVISOR = 5

    def create(self, display_unit: "DisplayUnit"):
        """
        the create method builds the SVG elements
        for a given unit and appends them to the unit's proxy.

        It has to call the _attach method to add the elements
        and if there's a text element, it has to call set_text_element to set
        the text element.

        The concrete class should provide appropriate CSS
        in a class field named _CSS.
        """
        ...

    @contextmanager
    def _attach(self, display_unit, element, *classes):
        try:
            yield
        finally:
            element.setAttribute("data-unit", display_unit.unit_id)
            for cl in classes:
                element.classList.add(cl)
            display_unit.proxy.appendChild(element)

    @classmethod
    def register(cls):
        if not cls.STYLE_CREATED and hasattr(cls, "_CSS"):
            style = js.document.createElement("style")
            style.innerHTML = cls._CSS
            js.document.head.appendChild(style)
            cls.STYLE_CREATED = True


class DisplayUnit:
    """The display component of a game unit."""

    def __init__(self, unit_id: str, unit_type: str, layout: HexLayout = None) -> None:
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.proxy = js.document.createElementNS("http://www.w3.org/2000/svg", "g")
        self.proxy.setAttribute("id", unit_id)
        self.proxy.setAttribute("data-unit-type", unit_type)
        self.proxy.setAttribute("display", "none")
        self.proxy.setAttribute("user-select", "none")
        self._hex = Hex(-2, -2, 4)  # Default off-map
        self._hex_layout = layout
        self.text_element = None

    def push_classes(self, *classes: Iterable[str]) -> None:
        for cl in classes:
            self.proxy.classList.add(cl)

    def set_text_element(self, element: "js.Element") -> None:
        self.text_element = element

    def set_text(self, text: str) -> None:
        if self.text_element:
            self.text_element.textContent = text

    def display_at(self, x: float, y: float) -> None:
        self.proxy.setAttribute("transform", f"translate({x},{y})")

    def _set_visible(self, value: bool) -> None:
        if value:
            self.proxy.setAttribute("display", "block")
        else:
            self.proxy.setAttribute("display", "none")

    def _get_visible(self) -> bool:
        return self.proxy.getAttribute("display") != "none"

    def _set_position(self, hex: Hex) -> None:
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

    def _set_rotation(self, angle: float) -> None:
        transform = self.proxy.getAttribute("transform")
        # Remove existing rotation if any
        if "rotate(" in transform:
            start = transform.index("rotate(")
            end = transform.index(")", start) + 1
            transform = transform[:start] + transform[end:]
        # Append new rotation
        transform += f" rotate({angle})"
        self.proxy.setAttribute("transform", transform)

    def _get_hilited(self) -> bool:
        return self.proxy.classList.contains("hilited")

    def _set_hilited(self, value: bool) -> None:
        if value:
            self.proxy.classList.add("hilited")
        else:
            self.proxy.classList.remove("hilited")

    def _set_enabled(self, value: bool) -> None:
        if value:
            self.proxy.classList.remove("disabled")
        else:
            self.proxy.classList.add("disabled")

    def _get_enabled(self) -> bool:
        return not self.proxy.classList.contains("disabled")

    def __repr__(self) -> str:
        return (
            f"<Unit id={self.unit_id} hex=({self._hex.i},{self._hex.j},{self._hex.k})>"
        )

    visible = property(_get_visible, _set_visible)
    position = property(_get_position, _set_position)
    rotation = property(_get_rotation, _set_rotation)
    hilited = property(_get_hilited, _set_hilited)
    enabled = property(_get_enabled, _set_enabled)
