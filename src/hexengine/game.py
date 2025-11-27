import logging
from .map import Map
from .document import element

class Game():
    def __init__(self):
        self.running = True
        container = element("map-container")
        map = element("map-canvas")
        svg = element("map-svg")
        assert map is not None, "Map canvas element not found"
        assert svg is not None, "Map SVG element not found"
        self.canvas = Map(container, map, svg)
        
        self.logger = logging.getLogger("game")
        self.logger.info("Game initialized")

        self.canvas.on_click < self.on_click

    def on_click(self, *args):
        logging.getLogger("map").info(f"Container clicked {args}")
        hex = self.canvas._hex_layout.pixel_to_hex(*args[-1])
        self.canvas.draw_hex(hex, fill="#D6FFDCFF", stroke="#00000000")
        logging.getLogger("map").info(f"{hex.i},{hex.j},{hex.k}")