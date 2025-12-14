import js  # pyright: ignore[reportMissingImports]
from ..hexes.types import Hex
from .layout import HexLayout


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

    def draw_hex(self, hex: Hex, fill="white", stroke="black"):
        points = self._hex_layout.hex_corners(hex)
        pointsString = " ".join([f"{x},{y}" for x, y in points])
        poly = js.document.createElementNS("http://www.w3.org/2000/svg", "polygon")
        poly.setAttribute("points", pointsString)
        poly.setAttribute("fill", fill)
        poly.setAttribute("stroke", stroke)
        self._svg.appendChild(poly)

    def draw_text(self, hex: Hex, text: str, font_size: int = 12):
        txt = js.document.createElementNS("http://www.w3.org/2000/svg", "text")
        x, y = self._hex_layout.hex_to_pixel(hex)
        txt.setAttribute("x", str(x))
        txt.setAttribute("y", str(y))
        txt.setAttribute("font-size", str(font_size))
        txt.setAttribute("fill", "black")
        txt.textContent = text
        self._svg.appendChild(txt)
