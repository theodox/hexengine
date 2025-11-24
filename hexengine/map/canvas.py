import logging
import js  # pyright: ignore[reportMissingImports]
from typing import Iterable
from functools import singledispatchmethod
from ..hexes.types import Hex
from ..document import element
from .layout import HexLayout
from .handler import Handler

class SVGCanvas:
    
    def __init__(self, svg_element: js.SVGElement):
        self._svg = svg_element

    # @property
    # def on_click(self):
    #     return self._click_handler
    
    # @property
    # def on_dblclick(self):
    #     return self._dblclick_handler

    # @property
    # def on_drag(self):
    #     return self._drag_handler
    
    # @property
    # def on_mouse_down(self):
    #     return self._mouse_down_handler
    
    # @property
    # def on_mouse_up(self):
    #     return self._mouse_up_handler

    # def get_click_coords(self, event) -> tuple[float, float]:
    #     rect = event.target.getBoundingClientRect()
    #     x = event.clientX - rect.left
    #     y = event.clientY - rect.top
    #     sx = self._svg.width.baseVal.value / rect.width
    #     sy = self._svg.height.baseVal.value / rect.height
    #     return (x *sx, y * sy)

class MapCanvas:
    """
    The background bitmap canvas for drawing hexagons.
    """
    def __init__(self, canvas_element: str):  
        self._canvas = canvas_element
        
        # Set canvas internal resolution to match CSS display size
        rect = self._canvas.getBoundingClientRect()
        self._canvas.width = int(rect.width)
        self._canvas.height = int(rect.height)
        
        hex_data = self._canvas.getAttribute("data-hexsize")
        if hex_data is not None:
            hex_size = float(hex_data)
        else:
            hex_size = 24.0
        self._context = self._canvas.getContext("2d")
        self._hex_layout = HexLayout(
            hex_size, self._canvas.width / 2, self._canvas.height / 2
        )
       
        self._hex_width = hex_size * 2
        self._hex_height = (3**0.5) * hex_size
  
    @property
    def canvas(self) -> js.HTMLCanvasElement:
        return self._canvas
    @property
    def context(self) -> js.CanvasRenderingContext2D:
        return self._context
    
    def draw_line(self, x1: float, y1: float, x2: float, y2: float, stroke="black"):
        self._context.beginPath()
        self._context.strokeStyle = stroke
        self._context.moveTo(x1, y1)
        self._context.lineTo(x2, y2)
        self._context.stroke()
        self._context.closePath()

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

    def draw_hex_rect(
        self,
        bottom_left: Hex,
        top_right: Hex,
        fill="white",
        stroke="black",
    ):
        for i in range(bottom_left.i, top_right.i + 1):
            for j in range(bottom_left.j, top_right.j + 1):
                k = -i - j
                hex = Hex(i, j, k)
                self.draw_hex(hex, fill=fill, stroke=stroke)

class Map:
    """
    A canvas for drawing hexagons.
    """
    def __init__(self, 
                 container_element: js.HTMLElement,
                 canvas_element: js.HTMLCanvasElement, 
                 svg_element: js.SVGElement):  
        self._container = container_element
        self._canvas = MapCanvas(canvas_element)
        self._svg = SVGCanvas(svg_element)

        self._hex_size= canvas_element.getAttribute("data-hexsize")
        
        if self._hex_size is not None:
            self._hex_size = float(self._hex_size)  
        else:
            self._hex_size = 24

        self._hex_layout = HexLayout(
            self._hex_size, 
            canvas_element.width / 2, 
            canvas_element.height / 2
        )
       
        self._hex_width = self._hex_size * 2
        self._hex_height = (3**0.5) * self._hex_size

        self._clickHandler = Handler(self._container, "click")
        self._clickHandler < self.on_click
      
    def on_click(self, *args):
        logging.getLogger("map").info(f"Container clicked {args}")
        pix = self.get_click_coords(args[0])
        logging.getLogger("map").info(f"Clicked at hex {pix}")
        hex = self._hex_layout.pixel_to_hex(*pix)
        logging.getLogger("map").info(f"Clicked at hex {hex}")
        self.canvas.draw_hex(hex, fill="#FF000027")

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
    def svg (self) -> MapCanvas:
        return self._svg
    
    def get_click_coords(self, event) -> tuple[float, float]:
        rect = event.target.getBoundingClientRect()
        x = event.clientX - rect.left
        y = event.clientY - rect.top
        sx = self._canvas.canvas.width / rect.width
        sy = self._canvas.canvas.height / rect.height
        return (x *sx, y * sy)
    # def draw_hex(self, hex: Hex, fill="white", stroke="black"):
    #     points = self._hex_layout.hex_corners(hex)
    #     points.append(points[0])  # Close the hexagon
    #     self._context.beginPath()
    #     self._context.strokeStyle = stroke
    #     self._context.fillStyle = fill
    #     for p in points:
    #         self._context.lineTo(*p)
    #         self._context.stroke()
    #     self._context.closePath()
    #     self._context.fill()

    # def draw_hexes(
    #     self,
    #     hexes: Iterable[Hex],
    #     fill="white",
    #     stroke="black",
    # ):
    #     for hex in hexes:
    #         self.draw_hex(hex, fill=fill, stroke=stroke)

    # def draw_text(
    #     self, hex: Hex, text: str, font: str = "10px Arial", color: str = "black"
    # ):
    #     x, y = self._hex_layout.hex_to_pixel(hex)
    #     self._context.fillStyle = color
    #     self._context.font = font
    #     self._context.fillText(text, x - self._hex_width / 4, y)

 
    # @singledispatchmethod
    # def __contains__(self, hex: Hex) -> bool:
    #     """
    #     Returns True if the hex is fully within the canvas bounds."""
    #     for p in self._hex_layout.hex_corners(hex):
    #         x, y = p
    #         if not (0 <= x <= self._canvas.canvas.width and 0 <= y <= self._canvas.canvas.height):
    #             return False
    #     return True

    # @__contains__.register
    # def __contains_pixel__(self, x: float, y: float) -> bool:
    #     """
    #     Returns True if the pixel coordinates are within the canvas bounds.
    #     """
    #     hex = self._hex_layout.pixel_to_hex(x, y)
    #     return self.__contains__(hex)

    
    # def get_click_coords(self, event) -> tuple[float, float]:
    #     rect = event.target.getBoundingClientRect()
    #     x = event.clientX - rect.left
    #     y = event.clientY - rect.top
    #     sx = self._canvas.canvas.width / rect.width
    #     sy = self._canvas.canvas.height / rect.height
    #     return (x *sx, y * sy)
