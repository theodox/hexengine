import js  # pyright: ignore[reportMissingImports]
from ..hexes.types import Hex
from .layout import HexLayout
from pyodide.ffi import create_proxy
import logging


class SVGLayer:
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

    def clear(self):
        for child in self._svg.childNodes:
            if child.classList.contains("highlight"):
                logging.info("Removing hex layer")
                child.classList.add("fade-out")
                js.setTimeout(create_proxy(lambda: self._svg.removeChild(child)), 250)

    def _draw_hex(self, hex: Hex, root: js.SVGElement):
        points = self._hex_layout.hex_corners(hex)
        pointsString = " ".join([f"{x},{y}" for x, y in points])
        poly = js.document.createElementNS("http://www.w3.org/2000/svg", "polygon")
        poly.setAttribute("points", pointsString)

        root.appendChild(poly)

    def draw_hexes(self, hexes: list[Hex], cls="highlight"):
        root = js.document.createElementNS("http://www.w3.org/2000/svg", "g")
        root.classList.add(cls)
        for hex in hexes:
            self._draw_hex(hex, root)
        self._svg.appendChild(root)

    def draw_hex(self, hex: Hex, cls="highlight"):
        self.draw_hexes([hex], cls=cls)

    def draw_text(self, hex: Hex, text: str, font_size: int = 12):
        txt = js.document.createElementNS("http://www.w3.org/2000/svg", "text")
        x, y = self._hex_layout.hex_to_pixel(hex)
        txt.setAttribute("x", str(x))
        txt.setAttribute("y", str(y))
        txt.setAttribute("font-size", str(font_size))
        txt.setAttribute("fill", "black")
        txt.textContent = text
        self._svg.appendChild(txt)
