import logging
from typing import Iterable

from ..document import js
from ..hexes.types import Hex, Cartesian
from .layout import HexLayout
from ..hexes.shapes import rectangle_from_corners


class CanvasLayer:
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

        w = (self._canvas.width - (self._hex_layout.origin_x * 2)) // hs
        h = (self._canvas.height - (self._hex_layout.origin_y * 2)) // hs

        logging.getLogger().info(
            f"Canvas size: {w}x{h}\n    hex size: {hex_layout.size}\n    grid size: {self._canvas.width}x{self._canvas.height}"
        )

        start = Hex.from_cartesian(Cartesian(0, 0))
        br = Hex.from_cartesian(Cartesian(w, h))

        self.draw_hex_rect(
            start,
            br,
            fill="#FFFFFF10",
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
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        stroke: str = "black",
        stroke_width: int = 1,
    ) -> None:
        self._context.beginPath()
        self._context.strokeStyle = stroke
        self._context.lineWidth = stroke_width
        self._context.moveTo(x1, y1)
        self._context.lineTo(x2, y2)
        self._context.stroke()
        self._context.closePath()

    def draw_hex(
        self,
        hex: Hex,
        fill: str = "white",
        stroke: str = "black",
        stroke_width: int = 1,
    ) -> None:
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
        self,
        hexes: Iterable[Hex],
        fill: str = "white",
        stroke: str = "black",
        stroke_width: int = 1,
    ) -> None:
        for hex in hexes:
            self.draw_hex(hex, fill=fill, stroke=stroke, stroke_width=stroke_width)

    def draw_hex_rect(
        self,
        top_left: Cartesian,
        bottom_right: Cartesian,
        fill: str = "white",
        stroke: str = "black",
        stroke_width: int = 1,
    ) -> None:
        rect = rectangle_from_corners(top_left, bottom_right)
        for hex in rect:
            self.draw_hex(hex, fill=fill, stroke=stroke, stroke_width=stroke_width)

    def redraw(self) -> None:
        """
        Redraw the canvas layer after a resize.
        Updates canvas dimensions to match current display size and redraws hex grid.
        """
        # Update canvas internal resolution to match current CSS display size
        rect = self._canvas.getBoundingClientRect()
        self._canvas.width = int(rect.width)
        self._canvas.height = int(rect.height)

        # Clear the canvas
        self._context.clearRect(0, 0, self._canvas.width, self._canvas.height)

        # Redraw hex grid
        hs = int(self._hex_layout.size)
        w = (self._canvas.width - (self._hex_layout.origin_x * 2)) // hs
        h = (self._canvas.height - (self._hex_layout.origin_y * 2)) // hs

        logging.getLogger().info(
            f"Canvas redraw: {w}x{h} hexes, canvas size: {self._canvas.width}x{self._canvas.height}"
        )

        start = Hex.from_cartesian(Cartesian(0, 0))
        br = Hex.from_cartesian(Cartesian(w, h))

        self.draw_hex_rect(
            start,
            br,
            fill="#FFFFFF10",
            stroke=self.hex_color,
            stroke_width=self.hex_stroke,
        )
