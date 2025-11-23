import time
from typing import Sequence, Iterable
from math import atan2, copysign, cos, sin, pi, sqrt, ceil, floor
from pyodide.ffi import create_proxy
import js
import logging
import sys

from . import dev_console
from .document import element
from .map import HexCanvas
from .hexes.math import Hex
from .hexes.shapes import  angle, convex_hull, path, polygon#, convex_polygon
from .excepthook import install_exception_hook
__version__ = "0.1.0"


def main():
    dev_console.initialize("", element("console"), element("console-input"), globals())
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.warning("Hexes demo starting...")
    install_exception_hook(logger)

    logger.debug(f"Hexes version: {__version__}")
    logger.debug(f"dir(hexes.shapes): {dir()}")


    hex_canvas = HexCanvas("map-canvas", 24)

    loading = element("loading")
    loading.style.display = "none"

    def map_fill(size: int) -> Iterable[Hex]:
        for x in range(-size, size + 1):
            for y in range(-size, size + 1):
                z = -x - y
                h = Hex(x, y, z)
                if h in hex_canvas:
                    yield h

    hex_canvas.draw_hexes(map_fill(19), fill="#d3d3d3", stroke="black")
    
    hex_canvas.canvas.mouseclick = create_proxy(
        lambda event: hex_canvas.on_canvas_click(event, hex_canvas.context)
    )
    hex_canvas.canvas.addEventListener("click", hex_canvas.canvas.mouseclick)


    examples = [Hex(-5, 0, 5),
                Hex(0,0,0) , Hex(-2, 0, 2),Hex(2, 7, 5), Hex(8, 1, -9), Hex(3, -6, 3)]
    hex_canvas.draw_hexes(examples, fill="#E28F1391", stroke="green")
    hull = convex_hull(examples)
    logger.debug(f"Convex hull of examples: {hull}")

    hex_canvas.draw_hexes(hull, fill="#1A121549", stroke="blue")
    
    outline = path(hull + [hull[0]])
    hex_canvas.draw_hexes(outline, fill="#2120165C", stroke="red")
    t = time.time()
    #for r in wedge_fill(Hex(0, 0, 0), 8, 0, 2 * pi / 3):
    #    hex_canvas.draw_hex(r, fill="#FF000027")
    logger.debug(f"wedge_fill time: {time.time() - t:.4f} seconds")

    logger.debug(f"Angle test: {angle(Hex(0, 0, 0), Hex(9, 0, -9)):.4f} radians")

    #wait delay(1000)
    hex_canvas.draw_hexes(polygon(hull), fill="#E28F1391", stroke="green")


    print(sys.excepthook)
    print (10 /0)