from enum import Enum
import logging
from .map import Map
from .map.mouse_handler import MouseHandler
from .document import element
from .hexes.types import Hex
from .dev_console import set_status
import js

from pyodide.ffi import create_proxy


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
        self.pending_click_timeout = None

        self.logger = logging.getLogger("game")
        self.logger.info("Game initialized")

        self.canvas.on_mouse_down < self.on_mouse_down
        self.canvas.on_mouse_up < self.on_mouse_up
        self.canvas.on_drag < self.on_drag

        # Add a test unit
        for r in range(6):
            u = self.canvas.add_unit(f"unit{r}", "soldier")
            u.position = Hex(10, r, -r - 10)
            u.visible = True

    def mouse_distance(self):
        dx = abs(self.drag_start[0] - self.drag_end[0])
        dy = abs(self.drag_start[1] - self.drag_end[1])
        return (dx**2 + dy**2) ** 0.5

    def on_mouse_down(self, *args):
        # Prevent default to stop text selection and default drag behavior
        args[0].preventDefault()

        # args[2] contains the properly calculated coordinates from Handler
        self.drag_start = (
            args[2] if len(args) > 2 else (args[0].offsetX, args[0].offsetY)
        )
        self.mouse_state = MouseState.DOWN

        # Walk up the tree to find element with data-unit
        target = args[0].target
        set_status(f"Target: {target} {self.mouse_state} {self.selection}")

        if target.id == "map-units":
            # Clicked on background
            if self.selection:
                self.selection.active = False
            self.selection = None
            self.logger.debug("Mouse down on background")
            return

        unit_id = None
        while target and not unit_id:
            unit_id = target.getAttribute("data-unit")
            if not unit_id:
                self.logger.warning(f"Walking up from {target} to parent")
                target = target.parentElement

        if unit_id:
            unit = self.canvas.units.get_unit(unit_id)
            # Only clear previous selection if clicking on a different unit
            if self.selection and self.selection != unit:
                self.selection.active = False
            unit.active = True
            self.selection = unit
            self.logger.debug(
                f"Mouse down at {self.drag_start}, target unit: {unit_id}, active: {unit.active}"
            )
        else:
            # Clicking on background - clear selection
            if self.selection:
                self.selection.active = False
            self.selection = None
            self.logger.warning("Mouse down on background")

    def on_drag(self, *args):
        if args[0].buttons != 1:
            self.mouse_state = MouseState.UP
            return

        # Prevent default to stop text selection during drag
        args[0].preventDefault()

        # args[2] contains the properly calculated coordinates from Handler
        self.drag_end = args[2] if len(args) > 2 else (args[0].offsetX, args[0].offsetY)
        self.mouse_state = MouseState.DRAGGING

        if not self.selection:
            return

        distance = self.mouse_distance()
        if distance > 12:
            # Place unit directly at cursor position
            self.selection.proxy.setAttribute(
                "transform", f"translate({self.drag_end[0]},{self.drag_end[1]})"
            )

    def on_mouse_up(self, *args):
        self.mouse_state = MouseState.UP
        target = args[0].target
        set_status(f"Target: {target} {self.mouse_state} {self.selection}")

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
                # Cancel pending single click
                if self.pending_click_timeout is not None:
                    js.clearTimeout(self.pending_click_timeout)
                    self.pending_click_timeout = None
                self.logger.debug(f"Double-click detected ({time_since_last_click} ms)")
                self.on_dbl_click(*args)
                self.last_click_time = 0  # Reset to prevent triple-click
            else:
                # Delay single click to check for double-click
                self.logger.debug(f"Click detected, waiting for potential double-click")
                if self.pending_click_timeout is not None:
                    js.clearTimeout(self.pending_click_timeout)

                self.pending_click_timeout = js.setTimeout(
                    create_proxy(lambda: self.on_click(*args)),
                    self.double_click_threshold,
                )
                self.last_click_time = current_time

    def on_click(self, *args):
        if self.selection:
            self.selection.active = False
            self.selection = None
            self.logger.debug("Click processed, unit snapped to grid")
        else:
            self.logger.debug("Click with no selection")

        self.last_click_time = 0

    def on_dbl_click(self, *args):
        self.logger.debug("Double click detected")
        if self.selection:
            # Example: toggle visibility on double-click
            # self.selection
            self.logger.debug(f"Double click on unit {self.selection.unit_id}")
            self.selection.active = False
            self.selection = None
            # self.selection.visible = not self.selection.visible
        else:
            self.logger.debug("double click with no selection")
        self.last_click_time = 0

    def snap_to_grid(self):
        x, y = self.drag_end
        h = self.canvas.hex_layout.pixel_to_hex(x, y)
        self.selection.position = h
