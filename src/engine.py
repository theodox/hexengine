import dataclasses
import time
from typing import Sequence, Iterable
from math import atan2, copysign, cos, sin, pi, sqrt, ceil, floor
from pyodide.ffi import create_proxy
import js
import logging

import dev_console
from document import element
from map import HexCanvas
from hexes.math import Hex, cube_round, normalize, neighbors, neighbor_hex, distance, lerp, line
from hexes.shapes import path, radius, ring, wedge, angle

__version__ = "0.1.0"




def main():
    dev_console.initialize("", element("console"))
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.warning("Hexes demo starting...")

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

    t = time.time()
    #for r in wedge_fill(Hex(0, 0, 0), 8, 0, 2 * pi / 3):
    #    hex_canvas.draw_hex(r, fill="#FF000027")
    logger.debug(f"wedge_fill time: {time.time() - t:.4f} seconds")

    logger.debug(f"Angle test: {angle(Hex(0, 0, 0), Hex(9, 0, -9)):.4f} radians")


if __name__ == "__main__":
    main()
