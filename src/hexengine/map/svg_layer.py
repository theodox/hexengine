from __future__ import annotations

import logging

from ..document import create_proxy, js
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

    def _remove_child_if_present(self, node) -> None:
        """Remove node from this SVG if still attached (safe for deferred calls)."""
        try:
            if node is not None and self._svg.contains(node):
                self._svg.removeChild(node)
        except Exception:
            pass

    def clear(self) -> None:
        # Snapshot nodes — childNodes is live; lambdas must capture each node, not loop var.
        for child in list(self._svg.childNodes):
            if child.classList.contains("highlight"):
                logging.info("Removing hex layer")
                child.classList.add("fade-out")
                js.setTimeout(
                    create_proxy(lambda c=child: self._remove_child_if_present(c)),
                    250,
                )

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
