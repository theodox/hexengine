from math import sqrt, cos, sin, pi
import js  # pyright: ignore[reportMissingImports]
from typing import Sequence, Iterable
import logging
from functools import singledispatchmethod
from pyodide.ffi import create_proxy
from .hexes.types import Hex
from .hexes import shapes
from .document import element


class HexLayout:
    """
    Converts between hex coordinates and pixel coordinates for flat-topped hexagons
    """

    def __init__(self, size: float, origin_x: float = 0.0, origin_y: float = 0.0):
        self.size = size
        self.origin_x = origin_x
        self.origin_y = origin_y

    def hex_to_pixel(self, hex: Hex) -> tuple[float, float]:
        x = self.size * (3 / 2 * hex.i) + self.origin_x
        y = self.size * ((3**0.5) * (hex.j + hex.i / 2)) + self.origin_y
        return (x, y)

    def pixel_to_hex(self, x: float, y: float) -> Hex:
        x = (x - self.origin_x) / self.size
        y = (y - self.origin_y) / self.size
        q = 2.0 / 3 * x
        r = -1.0 / 3 * x + sqrt(3) / 3 * y
        return Hex(round(q), round(r), round(-q - r))

    def hex_corners(self, hex: Hex) -> list[tuple[float, float]]:
        center_x, center_y = self.hex_to_pixel(hex)
        corners = []
        for i in range(6):
            angle = 2 * pi * i / 6
            corner_x = center_x + self.size * cos(angle)
            corner_y = center_y + self.size * sin(angle)
            corners.append((corner_x, corner_y))
        return corners

class Handler:
    def __init__(self, owner, event_type: str):
        self._handlers = []
        self._owner = owner
        self._event_type = event_type
        self.proxy = create_proxy(self._handle_event)
        self._owner.addEventListener(event_type, self.proxy)

    def _handle_event(self, event):
        logging.getLogger().debug(f"Handling event {event} in {self}")
        for handler in self._handlers:
            handler(event, self._owner.getContext("2d"))

    def __lt__(self, handler):  
        # use < to add a handler
        logging.getLogger().debug(f"Adding handler {handler} to {self}")
        self._handlers.append( create_proxy(handler))
        return self

    def __isub__(self, handler):
        raise NotImplemented

    def __repr__(self):
        return f"<Handler event_type={self._event_type} owner={self._owner}>"

class HexCanvas:
    """
    A canvas for drawing hexagons.
    """
    def __init__(self, canvas_id: str, hex_size):
        self._canvas = element(canvas_id)
        self._context = self._canvas.getContext("2d")
        self._hex_layout = HexLayout(
            hex_size, self._canvas.width / 2, self._canvas.height / 2
        )
        self._hex_width = hex_size * 2
        self._hex_height = (3**0.5) * hex_size
        self._click_handler = Handler(self._canvas, "click")
        self._dblclick_handler = Handler(self._canvas, "dblclick")
        
    @property
    def canvas(self) -> js.HTMLCanvasElement:
        return self._canvas
    @property
    def context(self) -> js.CanvasRenderingContext2D:
        return self._context
    
    @property
    def on_click(self):
        return self._click_handler
    
    @property
    def on_dblclick(self):
        return self._dblclick_handler

    def draw_hex(self, hex: Hex, fill="white", stroke="black"):
        points = self._hex_layout.hex_corners(hex)
        points.append(points[0])  # Close the hexagon
        self._context.beginPath()
        self._context.strokeStyle = stroke
        self._context.fillStyle = fill
        for p in points:
            self._context.lineTo(*p)
            self._context.stroke()
        self._context.closePath()
        self._context.fill()

    def draw_hexes(
        self,
        hexes: Iterable[Hex],
        fill="white",
        stroke="black",
    ):
        for hex in hexes:
            self.draw_hex(hex, fill=fill, stroke=stroke)

    def draw_text(
        self, hex: Hex, text: str, font: str = "10px Arial", color: str = "black"
    ):
        x, y = self._hex_layout.hex_to_pixel(hex)
        self._context.fillStyle = color
        self._context.font = font
        self._context.fillText(text, x - self._hex_width / 4, y)

 
    @singledispatchmethod
    def __contains__(self, hex: Hex) -> bool:
        """
        Returns True if the hex is fully within the canvas bounds."""
        for p in self._hex_layout.hex_corners(hex):
            x, y = p
            if not (0 <= x <= self._canvas.width and 0 <= y <= self._canvas.height):
                return False
        return True

    @__contains__.register
    def __contains_pixel__(self, x: float, y: float) -> bool:
        """
        Returns True if the pixel coordinates are within the canvas bounds.
        """
        hex = self._hex_layout.pixel_to_hex(x, y)
        return self.__contains__(hex)

    
    def get_click_coords(self, event) -> tuple[float, float]:
        rect = event.target.getBoundingClientRect()
        x = event.clientX - rect.left
        y = event.clientY - rect.top
        sx = self._canvas.width / rect.width
        sy = self._canvas.height / rect.height
        return (x *sx, y * sy)


  