import js  # pyright: ignore[reportMissingImports]
from typing import Iterable
from ..hexes.types import Hex
from .layout import HexLayout
from .handler import UIEventHandler
from .unit_layer import UnitLayer
from .svg_layer import SVGLayer
from .canvas_layer import CanvasLayer
from ..units import DisplayUnit, GameUnit
import logging


class Map:
    """
    A canvas for drawing hexagons.
    """

    def __init__(
        self,
        container_element: js.HTMLElement,
        canvas_element: js.HTMLCanvasElement,
        svg_element: js.SVGElement,
        unit_element: js.SVGElement,
    ):
        self._container = container_element

        self._hex_size = canvas_element.getAttribute("data-hexsize")
        self._hex_color = canvas_element.getAttribute("data-hexcolor")
        self._hex_stroke = int(canvas_element.getAttribute("data-hexstroke"))
        self._hex_margin = int(canvas_element.getAttribute("data-hexmargin"))
        logging.getLogger().warning(
            f"Hex size: {self._hex_size}, color: {self._hex_color}, stroke: {self._hex_stroke}"
        )

        if self._hex_size is not None:
            self._hex_size = float(self._hex_size)
        else:
            self._hex_size = 24

        self._hex_layout = HexLayout(
            self._hex_size,
            self._hex_size + self._hex_margin,
            self._hex_size + self._hex_margin,
        )

        # Set CSS variables for unit sizing based on hex layout
        unit_size = (int(self._hex_layout.size * 1.5)) - 2
        js.document.documentElement.style.setProperty("--unit-width", f"{unit_size}px")
        js.document.documentElement.style.setProperty("--unit-height", f"{unit_size}px")

        self._canvas_layer = CanvasLayer(
            canvas_element, self._hex_layout, self._hex_color, self._hex_stroke
        )
        self._svg_layer = SVGLayer(
            svg_element, self._hex_layout, self._hex_color, self._hex_stroke
        )
        self._unit_layer = UnitLayer(
            unit_element, self._hex_layout, self._hex_color, self._hex_stroke
        )

        self._dragHandler = UIEventHandler(self._container, "mousemove")
        self._mouse_downHandler = UIEventHandler(self._container, "mousedown")
        self._mouse_upHandler = UIEventHandler(self._container, "mouseup")

    @property
    def on_drag(self):
        return self._dragHandler

    @property
    def on_mouse_down(self):
        return self._mouse_downHandler

    @property
    def on_mouse_up(self):
        return self._mouse_upHandler

    @property
    def hex_size(self) -> float:
        return self._hex_size

    @property
    def hex_layout(self) -> HexLayout:
        return self._hex_layout

    @property
    def canvas(self) -> CanvasLayer:
        return self._canvas

    @property
    def svg(self) -> CanvasLayer:
        return self._svg

    @property
    def units(self) -> UnitLayer:
        return self._unit_layer

    def draw_hex(self, hex: Hex, fill="white", stroke="black"):
        self._svg_layer.draw_hex(hex, fill=fill, stroke=stroke)

    def draw_hexes(self, hexes: Iterable[Hex], fill="white", stroke="black"):
        for hex in hexes:
            self.draw_hex(hex, fill=fill, stroke=stroke)

    def draw_bg_hexes(self, hexes: Iterable[Hex], fill="white", stroke="black"):
        for hex in hexes:
            self.draw_bg_hex(hex, fill=fill, stroke=stroke)

    def draw_bg_hex(self, hex: Hex, fill="white", stroke="black"):
        points = self._hex_layout.hex_corners(hex)
        points.append(points[0])  # Close the hexagon
        self.canvas.context.beginPath()
        self.canvas.context.strokeStyle = stroke
        self.canvas.context.fillStyle = fill
        for p in points:
            self.canvas.context.lineTo(*p)
            self.canvas.context.stroke()
        self.canvas.context.closePath()
        self.canvas.context.fill()

    def add_unit(self, unit: GameUnit):
        self._unit_layer.add_unit(unit)
