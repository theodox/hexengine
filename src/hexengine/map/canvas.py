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

        hs = int(hex_layout.size)

        w = (self._canvas.width - (self._hex_layout.origin_x * 2)) //  hs
        h = (self._canvas.height - (self._hex_layout.origin_y * 2)) // hs

        logging.getLogger().info(
            f"Canvas size: {w}x{h}\n    hex size: {hex_layout.size}\n    grid size: {self._canvas.width}x{self._canvas.height}"
        )

        # this is sloppy way to draw the grid background
        # overlay -- the slop is there to extend the hex lines
        # past the edges of the canvas to avoid gaps, but
        # this is not the best way to do this.
        start = Hex.from_cartesian(Cartesian(-2, -2))
        br = Hex.from_cartesian(Cartesian(w+2, h+2))

        self.draw_hex_rect(
            start,
            br,
            fill="#00000000",
            stroke=self.hex_color,
            stroke_width=self.hex_stroke,
        )

        test = Hex.from_cartesian(Cartesian(10,10))
        test2 = Hex.from_cartesian(Cartesian(20,20))
        self.draw_hex_rect(
           test, test2, fill="#29E11433", stroke="#000000FF", stroke_width=0
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
        for x in range(tl.x, br.x + 1):
            for y in range(tl.y, br.y + 1):
                h = cartesian_int_to_hex(Cartesian(x, y))
                #logging.getLogger().debug(f"Drawing hex at {h} for cartesian {x},{y}")
                self.draw_hex(h, fill=fill, stroke=stroke, stroke_width=stroke_width)


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
