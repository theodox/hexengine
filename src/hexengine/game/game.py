from asyncio.log import logger
import logging
from ..map import Map
from ..map.mouse_handler import MouseHandler
from ..document import element
from ..hexes.types import Hex
from ..dev_console import set_status
import js
from ..hexes.shapes import radius

from pyodide.ffi import create_proxy

from .events import EventHandlerMixin, MouseState
from .popups import PopupManager, Popup

class Game(EventHandlerMixin):
    def __init__(self):
        self.running = True
        container = element("map-container")
        map = element("map-canvas")
        svg = element("map-svg")
        units = element("map-units")
        self.popup_manager = PopupManager(container)
        

        assert map is not None, "Map canvas element not found"
        assert svg is not None, "Map SVG element not found"
        self.canvas = Map(container, map, svg, units)

        self.click_time = 0
        self.last_click_time = 0
        self.drag_start = (0, 0)
        self.drag_end = (0, 0)
        self.selection = None
        self.mouse_state = MouseState.UP
        self.double_click_threshold = 300  # milliseconds
        self.pending_click_timeout = None

        self.logger = logging.getLogger("game")
        self.logger.info("Game initialized")

        self.canvas.on_mouse_down < self.on_mouse_down
        self.canvas.on_mouse_up < self.on_mouse_up
        self.canvas.on_drag < self.on_drag


    def mouse_distance(self):
        dx = abs(self.drag_start[0] - self.drag_end[0])
        dy = abs(self.drag_start[1] - self.drag_end[1])
        return (dx**2 + dy**2) ** 0.5

    def snap_to_grid(self):
        x, y = self.drag_end
        h = self.canvas.hex_layout.pixel_to_hex(x, y)
        self.selection.position = h
