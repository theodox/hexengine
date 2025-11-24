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

     