import logging

from ..document import js, create_proxy
from ..hexes.types import Hex
from .layout import HexLayout


class SVGLayer:
    SVG = "http://www.w3.org/2000/svg"

    def __init__(
        self,
        svg_element: js.SVGElement,
        hex_layout: HexLayout,
        hex_color: str,
        hex_stroke: int,
    ) -> None:
        self._svg = svg_element
        self._hex_layout = hex_layout
        self._hex_color = hex_color
        self._hex_stroke = hex_stroke

    def clear(self) -> None:
        for child in self._svg.childNodes:
            if child.classList.contains("highlight"):
                logging.info("Removing hex layer")
                child.classList.add("fade-out")
                js.setTimeout(create_proxy(lambda: self._svg.removeChild(child)), 250)

    def _draw_hex(self, hex: Hex, root: js.SVGElement) -> None:
        points = self._hex_layout.hex_corners(hex)
        pointsString = " ".join([f"{x},{y}" for x, y in points])
        poly = js.document.createElementNS(self.SVG, "polygon")
        poly.setAttribute("points", pointsString)

        root.appendChild(poly)

    def draw_hexes(self, hexes: list[Hex], cls: str = "highlight") -> None:
        root = js.document.createElementNS(self.SVG, "g")
        root.classList.add(cls)
        for hex in hexes:
            self._draw_hex(hex, root)
        self._svg.appendChild(root)

    def draw_hex(self, hex: Hex, cls: str = "highlight") -> None:
        self.draw_hexes([hex], cls=cls)

    def draw_text(self, hex: Hex, text: str, font_size: int = 12) -> None:
        txt = js.document.createElementNS(self.SVG, "text")
        x, y = self._hex_layout.hex_to_pixel(hex)
        txt.setAttribute("x", str(x))
        txt.setAttribute("y", str(y))
        txt.setAttribute("font-size", str(font_size))
        txt.setAttribute("fill", "black")
        txt.textContent = text
        self._svg.appendChild(txt)
