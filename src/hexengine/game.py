import logging
from .map import Map
from .document import element
from .hexes.types import Hex

class Game:
    def __init__(self):
        self.running = True
        container = element("map-container")
        map = element("map-canvas")
        svg = element("map-svg")
        units = element("map-units")
        assert map is not None, "Map canvas element not found"
        assert svg is not None, "Map SVG element not found"
        self.canvas = Map(container, map, svg, units)

        self.logger = logging.getLogger("game")
        self.logger.info("Game initialized")

        self.canvas.on_click < self.on_click

        self.canvas.draw_unit(Hex(7, 5, -12), unit_type="soldier", fill="#FF0000", stroke="#000000") 

    def on_click(self, *args):
        logging.getLogger("map").info(f"Container clicked {args}")
        hex = self.canvas._hex_layout.pixel_to_hex(*args[-1])
        self.canvas.draw_hex(hex, fill="#D6FFDCFF", stroke="#00000000")
        logging.getLogger("map").info(f"{hex.i},{hex.j},{hex.k}")
