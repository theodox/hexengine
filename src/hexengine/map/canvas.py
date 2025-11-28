import logging
import js  # pyright: ignore[reportMissingImports]
from typing import Iterable
from functools import singledispatchmethod
from ..hexes.types import Hex, Cartesian
from ..document import element
from .layout import HexLayout
from .handler import Handler
from ..hexes.shapes import polygon, convex_polygon
from ..hexes.math import hex_to_cartesian_int, cartesian_int_to_hex, SQRT_THREE


class SVGCanvas:
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
        polygon = js.document.createElementNS("http://www.w3.org/2000/svg", "polygon")
        polygon.setAttribute("points", pointsString)
        polygon.setAttribute("fill", fill)
        polygon.setAttribute("stroke", stroke)
        self._svg.appendChild(polygon)


class MapCanvas:
    """
    The background bitmap canvas for drawing hexagons.
    """

    def __init__(
        self,
        canvas_element: str,
        hex_layout: HexLayout,
        hex_color: str,
        hex_stroke: int,
    ):
        self._canvas = canvas_element
        self._context = self._canvas.getContext("2d")
        # Set canvas internal resolution to match CSS display size
        rect = self._canvas.getBoundingClientRect()
        self._canvas.width = int(rect.width)
        self._canvas.height = int(rect.height)
        self._hex_layout = hex_layout
        self.hex_color = hex_color
        self.hex_stroke = hex_stroke

        w = (self._canvas.width - (self._hex_layout.origin_x * 2)) // int(
            hex_layout.size
        )
        h = (self._canvas.height - (self._hex_layout.origin_y * 2)) // int(
            hex_layout.size
        )  # * SQRT_THREE)

        logging.getLogger().info(
            f"Canvas size: {w}x{h}, hex size: {hex_layout.size}, grid size: {w}x{h}"
        )

        start = Hex(0, 0, 0)
        br = Hex.from_cartesian(Cartesian(w, h))

        logging.getLogger().debug(
            f"Canvas size set to {self._canvas.width}x{self._canvas.height}"
        )
        self.draw_hex_rect(
            start,
            br,
            fill="#00000000",
            stroke=self.hex_color,
            stroke_width=self.hex_stroke,
        )

    @property
    def canvas(self) -> js.HTMLCanvasElement:
        return self._canvas

    @property
    def context(self) -> js.CanvasRenderingContext2D:
        return self._context

    def draw_line(
        self, x1: float, y1: float, x2: float, y2: float, stroke="black", stroke_width=1
    ):
        self._context.beginPath()
        self._context.strokeStyle = stroke
        self._context.lineWidth = stroke_width
        self._context.moveTo(x1, y1)
        self._context.lineTo(x2, y2)
        self._context.stroke()
        self._context.closePath()

    def draw_hex(self, hex: Hex, fill="white", stroke="black", stroke_width=1):
        points = self._hex_layout.hex_corners(hex)
        points.append(points[0])  # Close the hexagon
        self._context.beginPath()
        self._context.strokeStyle = stroke
        self._context.lineWidth = stroke_width
        self._context.fillStyle = fill
        for p in points:
            self._context.lineTo(*p)
            self._context.stroke()
        self._context.closePath()
        self._context.fill()

    def draw_hexes(
        self, hexes: Iterable[Hex], fill="white", stroke="black", stroke_width=1
    ):
        for hex in hexes:
            self.draw_hex(hex, fill=fill, stroke=stroke, stroke_width=stroke_width)

    def draw_hex_rect(
        self,
        top_left: Cartesian,
        bottom_right: Cartesian,
        fill="white",
        stroke="black",
        stroke_width=1,
    ):
        tl = Cartesian.from_hex(top_left)
        br = Cartesian.from_hex(bottom_right)
        bl = Cartesian(0, br.y)
        tr = Cartesian(br.x, 0)
        logging.getLogger().warning(f"Drawing hex rect corners:{tl} {tr}, {br}, {bl}")

        a = Hex.from_cartesian(tl)
        b = Hex.from_cartesian(tr)
        c = Hex.from_cartesian(br)
        d = Hex.from_cartesian(bl)

        rect = convex_polygon((a, b, c, d))
        self.draw_hexes(rect, fill=fill, stroke=stroke, stroke_width=stroke_width)


class Map:
    """
    A canvas for drawing hexagons.
    """

    def __init__(
        self,
        container_element: js.HTMLElement,
        canvas_element: js.HTMLCanvasElement,
        svg_element: js.SVGElement,
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

        self._canvas = MapCanvas(
            canvas_element, self._hex_layout, self._hex_color, self._hex_stroke
        )
        self._svg = SVGCanvas(
            svg_element, self._hex_layout, self._hex_color, self._hex_stroke
        )

        self._clickHandler = Handler(self._container, "click")
        self._dblclickHandler = Handler(self._container, "dblclick")
        self._dragHandler = Handler(self._container, "mousemove")
        self._mouse_downHandler = Handler(self._container, "mousedown")
        self._mouse_upHandler = Handler(self._container, "mouseup")

    @property
    def on_click(self):
        return self._clickHandler

    @property
    def on_dblclick(self):
        return self._dblclickHandler

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
    def canvas(self) -> MapCanvas:
        return self._canvas

    @property
    def svg(self) -> MapCanvas:
        return self._svg

    def draw_hex(self, hex: Hex, fill="white", stroke="black"):
        self._svg.draw_hex(hex, fill=fill, stroke=stroke)

    def draw_hexes(self, hexes: Iterable[Hex], fill="white", stroke="black"):
        for hex in hexes:
            self.draw_hex(hex, fill=fill, stroke=stroke)

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

    def draw_text(
        self, hex: Hex, text: str, font: str = "10px Arial", color: str = "black"
    ):
        x, y = self._hex_layout.hex_to_pixel(hex)
        self.canvas._context.fillStyle = color
        self.canvas._context.font = font
        self.canvas._context.fillText(text, x - 6, y)
