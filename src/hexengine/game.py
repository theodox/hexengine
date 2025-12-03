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

        self.click_time = 0
        self.last_click_time = 0
        self.drag_start = (0, 0)
        self.drag_end = (0, 0)
        self.selection = None
        self.mouse_state = MouseState.UP
        self.double_click_threshold = 300  # milliseconds

        self.logger = logging.getLogger("game")
        self.logger.info("Game initialized")

        self.canvas.on_mouse_down < self.on_mouse_down
        self.canvas.on_mouse_up < self.on_mouse_up
        self.canvas.on_drag < self.on_drag
  
        # Add a test unit
        for r in range(6):
            u = self.canvas.add_unit(f"unit{r}", "soldier")
            u.position = Hex(10, r,-r -10)
            u.visible = True

        self.dummy = element("xxx")
       
    def mouse_distance(self):
        dx = abs(self.drag_start[0] - self.drag_end[0])
        dy = abs(self.drag_start[1] - self.drag_end[1])
        return (dx ** 2 + dy ** 2) ** 0.5

    def on_mouse_down(self, *args):
        if self.selection:
            self.selection.active = False

        # args[2] contains the properly calculated coordinates from Handler
        self.drag_start = args[2] if len(args) > 2 else (args[0].offsetX, args[0].offsetY)
        self.mouse_state = MouseState.DOWN

        # Walk up the tree to find element with data-unit
        target = args[0].target
        self.dummy.value = f"Target id: {target.id} {self.mouse_state} {self.selection}"
    
        logging.getLogger("game").debug(f"Mouse down at {self.drag_start}, target element id: {target.id}")
        unit_id = None
        while target and not unit_id:
            unit_id = target.getAttribute("data-unit")
            if not unit_id:
                target = target.parentElement
        
        if unit_id:
            unit = self.canvas.units.get_unit(unit_id)
            unit.active = True
            self.selection = unit
            self.logger.debug(f"Mouse down at {self.drag_start}, target unit: {unit_id}, active: {unit.active}")
        else:
            self.selection = None
            self.logger.debug("Mouse down on background")
    
    def on_drag(self, *args):
        if args[0].buttons != 1:
            self.mouse_state = MouseState.UP
            return
        
        # args[2] contains the properly calculated coordinates from Handler
        self.drag_end = args[2] if len(args) > 2 else (args[0].offsetX, args[0].offsetY)
        self.mouse_state = MouseState.DRAGGING

        if not self.selection:
            return
        
        distance = self.mouse_distance()
        if distance > 12:
            # Place unit directly at cursor position
            self.selection.proxy.setAttribute("transform", f"translate({self.drag_end[0]},{self.drag_end[1]})")

    def on_mouse_up(self, *args):
        self.mouse_state = MouseState.UP
        target = args[0].target
        self.dummy.value = f"Target id: {target.id} {self.mouse_state} {self.selection}"

        self.drag_end = args[2] if len(args) > 2 else (args[0].offsetX, args[0].offsetY)
        if not self.selection:
            self.logger.debug("Mouse up with no selection")
            return

        current_time = js.Date.now()
        distance = self.mouse_distance()
        self.snap_to_grid()
        if distance < 12:
            # Check if this is a double-click
            time_since_last_click = current_time - self.last_click_time
            if time_since_last_click < self.double_click_threshold:
                self.logger.debug(f"Double-click detected ({time_since_last_click} ms)")
                self.on_dbl_click(*args)
                self.last_click_time = 0  # Reset to prevent triple-click
            else:
                self.logger.debug(f"Single click detected")
                self.on_click(*args)
                self.last_click_time = current_time

    def on_click(self, *args):
        if self.selection:
            self.selection.active = False
            self.selection = None
            logging.getLogger("game").debug("Click processed, unit snapped to grid")
        else:
            logging.getLogger("game").debug("Click with no selection")

    def on_dbl_click(self, *args):
        logging.getLogger("game").debug("Double click detected")
        if self.selection:
            # Example: toggle visibility on double-click
            self.selection.visible = not self.selection.visible
            self.selection.active = False
            self.selection = None
        else:
            logging.getLogger("game").debug("Click with no selection")

    def on_dbl_click(self, *args):
        logging.getLogger("game").debug("Double click detected")
        #self.selection.visible = not self.selection.visible
        self.snap_to_grid()
        

    def snap_to_grid(self):
        x, y = self.drag_end
        h = self.canvas.hex_layout.pixel_to_hex(x, y)
        self.selection.position = h
     