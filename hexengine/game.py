import logging
from .map import HexCanvas


class Game():
    def __init__(self, canvas_id: str, hex_size: float  = 30.0):
        self.running = True
        self.canvas = HexCanvas(canvas_id, hex_size)
        self.logger = logging.getLogger("game")
        self.logger.info("Game initialized")