from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
from typing import Protocol

from ..document import js
from ..hexes.types import Hex
from ..map.layout import HexLayout


class GraphicsCreator(Protocol):
    BASE_CLASSES = ("unit",)
    STYLE_CREATED = False

    # Display constants
    UNIT_SIZE_DIVISOR = 1.5
    HEAD_RADIUS_DIVISOR = 5

    def create(self, display_unit: DisplayUnit):
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

    STACK_OFFSET = 0.08

    def __init__(
        self,
        unit_id: str,
        unit_type: str,
        layout: HexLayout | None = None,
        *,
        unit_size_multiplier: float = 1.5,
    ) -> None:
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.unit_size_multiplier = float(unit_size_multiplier)
        # Stacking support (visual): lower index is logically "earlier" in the stack.
        self.stack_index: int = 0
        self.proxy = js.document.createElementNS("http://www.w3.org/2000/svg", "g")
        self.proxy.setAttribute("id", unit_id)
        self.proxy.setAttribute("data-unit", unit_id)  # For event handling
        self.proxy.setAttribute("data-unit-type", unit_type)
        self.proxy.setAttribute("display", "none")
        self.proxy.style.pointerEvents = "all"  # Make sure it receives mouse events
        self._hex = Hex(-2, -2, 4)  # Default off-map
        self._hex_layout = layout
        self.text_element = None
        self.glyph_element = None
        self.caption_element = None

    def push_classes(self, *classes: Iterable[str]) -> None:
        for cl in classes:
            self.proxy.classList.add(cl)

    def set_text_element(self, element: js.Element) -> None:
        self.text_element = element

    def set_glyph_element(self, element: js.Element) -> None:
        self.glyph_element = element

    def set_caption_element(self, element: js.Element) -> None:
        self.caption_element = element

    def set_text(self, text: str) -> None:
        """Update caption if present (e.g. counter health); else legacy single text node."""
        if self.caption_element is not None:
            self.caption_element.textContent = text
        elif self.text_element:
            self.text_element.textContent = text

    def set_glyph(self, text: str) -> None:
        if self.glyph_element is not None:
            self.glyph_element.textContent = text

    def set_caption(self, text: str) -> None:
        if self.caption_element is not None:
            self.caption_element.textContent = text

    def display_at(self, x: float, y: float) -> None:
        """
        Set unit position directly in pixels.
        Note: When used during drag preview, coordinates should be in map space
        (inverse-transformed) since the parent SVG has CSS transforms applied.
        """
        self.proxy.setAttribute("transform", f"translate({x},{y})")

    def display_at_screen(
        self, screen_x: float, screen_y: float, zoom: float, pan_x: float, pan_y: float
    ) -> None:
        """
        Set unit position in screen coordinates, accounting for parent CSS transform.

        CSS transform: translate(pan_x, pan_y) scale(zoom)
        For a child SVG element at position (x, y), the final screen position is:
        - (x * zoom + pan_x, y * zoom + pan_y)

        So to get (x, y) from screen coordinates:
        - x = (screen_x - pan_x) / zoom
        - y = (screen_y - pan_y) / zoom
        """
        map_x = (screen_x - pan_x) / zoom
        map_y = (screen_y - pan_y) / zoom

        self.proxy.setAttribute("transform", f"translate({map_x},{map_y})")

    def _set_visible(self, value: bool) -> None:
        if value:
            self.proxy.setAttribute("display", "block")
            self.proxy.style.visibility = "visible"
        else:
            self.proxy.setAttribute("display", "none")
            self.proxy.style.visibility = "hidden"

    def _get_visible(self) -> bool:
        return self.proxy.getAttribute("display") != "none"

    def _set_position(self, hex: Hex) -> None:
        self._hex = hex
        x, y = self._hex_layout.hex_to_pixel(self._hex)
        # Offset stacked units up/left by 5% of hex size per layer.
        # Hex size is `HexLayout.size` (radius-like scalar used by hex_to_pixel).

        d = float(self._hex_layout.size) * self.STACK_OFFSET * float(self.stack_index)
        x -= d
        y -= d
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
