from enum import Enum
import logging
from .map import Map
from .map.mouse_handler import MouseHandler
from .document import element
from .hexes.types import Hex
import js

class MouseState(Enum):
    UP = 0
    DOWN = 1
    DRAGGING = 2


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
        self.click_time = -1000
        self.click_start = (0, 0)
        self.click_end = (0, 0)
        self.mouse_state = MouseState.UP

        self.logger = logging.getLogger("game")
        self.logger.info("Game initialized")

        self.canvas.on_mouse_down < self.on_mouse_down
        self.canvas.on_mouse_up < self.on_mouse_up
        self.canvas.on_drag < self.on_drag
  
        # Add a test unit
        for r in range(6):
            u = self.canvas.add_unit(f"unit{r}", "soldier")
            u.position = Hex(0, r,-r)
            u.visible = True

        self.selection = None
       
    def on_mouse_down(self, *args):
        self.click_start = (args[0].offsetX, args[0].offsetY)
        self.mouse_state = MouseState.DOWN

        unit_id = args[0].target.getAttribute("data-unit")
        if self.selection:
            self.selection.active = False

        if unit_id:
            unit = self.canvas.units.get_unit(unit_id)
            unit.active = not unit.active
            self.selection = unit
            self.logger.debug(f"Mouse down at {self.click_start}, target unit: {unit_id}")
        else:
            self.logger.debug("Mouse down")
    
    def on_drag(self, *args):
        self.click_end = (args[0].offsetX, args[0].offsetY)
        self.mouse_state = MouseState.DRAGGING
        if args[0].buttons != 1:
            return
        if self.selection:
            dx = abs(self.click_start[0] - self.click_end[0])
            dy = abs(self.click_start[1] - self.click_end[1])
            distance = (dx ** 2 + dy ** 2) ** 0.5
            if distance > 12:   
                self.selection.proxy.setAttribute("transform", f"translate{self.click_end}")
        else:
            self.logger.debug("Dragging with no selection")

    def on_mouse_up(self, *args):
        self.mouse_state = MouseState.UP
        if not self.selection:
            self.logger.debug("Mouse up with no selection")
            return
        delta = js.Date.now() - self.click_time
        dx = abs(self.click_start[0] - self.click_end[0])
        dy = abs(self.click_start[1] - self.click_end[1])
        distance = (dx ** 2 + dy ** 2) ** 0.5
        if distance < 20:
            self.logger.debug(f"Mouse up after {delta} ms, considered a click")
            self.on_click(*args)        
        else:
            logging.getLogger("game").debug(f"Mouse up after {delta} ms, move distance {distance}")
            self.snap_to_grid()
            self.selection.active = False
            self.selection = None

    def on_click(self, *args):

        #logging.getLogger("map").debug(f">{args[0].target.id}< clicked")

        if self.selection:
            self.snap_to_grid()
            self.selection.active = False
            self.selection = None
        else:
            logging.getLogger("game").debug("Click with no selection")

    def on_dbl_click(self, *args):
        logging.getLogger("game").debug("Double click detected")
        self.selection.visible = not self.selection.visible
        self.snap_to_grid()
        

    def snap_to_grid(self):
        x, y = self.click_end
        h = self.canvas.hex_layout.pixel_to_hex(x, y)
        self.selection.position = h
     