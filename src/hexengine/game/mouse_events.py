from enum import Enum
import js
from pyodide.ffi import create_proxy
from ..dev_console import set_status
from ..hexes.shapes import radius
from ..map.handler import Handler, Modifiers
from ..actions import Move


class MouseState(Enum):
    UP = 0
    DOWN = 1
    DRAGGING = 2


class TargetType(Enum):
    UNIT = "unit"
    BACKGROUND = "background"


class EventHandlerMixin:
    """Mixin class providing mouse event handling functionality for the Game class."""

    MIN_DRAG_DISTANCE = 16  # pixels
    DBL_CLICK_THRESHOLD = 330  # milliseconds

    pending_click_timeout = None

    def _mouse_distance(self):
        dx = abs(self.drag_start[0] - self.drag_end[0])
        dy = abs(self.drag_start[1] - self.drag_end[1])
        return (dx**2 + dy**2) ** 0.5

    def _snap_to_grid(self):
        if not self.selection:
            return
        x, y = self.drag_end
        h = self.canvas.hex_layout.pixel_to_hex(x, y)
        if h in self.board.constraints:
            move = Move(self.selection.unit_id, self.selection.position, h)
            self.enqueue(move)
        else:
            orig = self.canvas.hex_layout.pixel_to_hex(*self.drag_start)
            self.selection.position = orig
            # no move

    def on_mouse_down(self, event, source, position, modifiers):
        # Prevent default to stop text selection and default drag behavior
        event.preventDefault()

        # position contains the properly calculated coordinates from Handler
        self.drag_start = position if position else (event.offsetX, event.offsetY)
        self.mouse_state = MouseState.DOWN

        target_type, unit = self._get_target(event)
        set_status(f"Target: {unit} {self.mouse_state} {self.selection},{modifiers}")
        # Walk up the tree to find element with data-unit
        if target_type == TargetType.BACKGROUND:
            self._bg_mousedown(modifiers)
        else:
            self._unit_mousedown(unit, modifiers)

    def on_drag(self, event, source, position, modifiers):
        if event.buttons != 1:
            self.mouse_state = MouseState.UP
            return

        # Prevent default to stop text selection during drag
        event.preventDefault()

        self.drag_end = position if position else (event.offsetX, event.offsetY)
        self.mouse_state = MouseState.DRAGGING

        if not self.selection:
            self._bg_drag(event, source, position, modifiers)
        else:
            self._unit_drag(event, source, position, modifiers)

    def on_mouse_up(self, event, source, position, modifiers):
        self.logger.warning((event, source, position, modifiers))
        self.mouse_state = MouseState.UP
        target = event.target
        set_status(f"Target: {target} {self.mouse_state} {self.selection}")

        target_type, unit = self._get_target(event)

        self.logger.warning(f"Mouse up on {target_type} {unit}")

        self.drag_end = position

        if target_type == TargetType.BACKGROUND:
            self._bg_mouseup(event, source, position, modifiers)
        else:
            self._unit_mouseup(event, source, position, modifiers)

    def _get_target(self, event):
        target = event.target

        if target.id == "map-units":
            return TargetType.BACKGROUND, None

        unit_id = None
        while target and not unit_id:
            unit_id = target.getAttribute("data-unit")
            target = target.parentElement
        unit = self.board.get_unit(unit_id)
        assert f"{unit} is not a clickable unit"
        return TargetType.UNIT, unit

    # ---------------------
    # background events
    # ---------------------

    def _bg_click(self, event, source, position, modifiers):
        self.logger.debug("Click on background")
        self.selection = None
        self.last_click_time = 0

    def _bg_dbl_click(self, event, source, position, modifiers):
        self.logger.debug("Double click on background")
        if self.selection:
            self.selection = None
            self.logger.debug("Double click processed, unit snapped to grid")
        else:
            self.logger.debug("Double click with no selection")
        self.last_click_time = 0

    def _bg_drag(self, event, source, position, modifiers):
        distance = self._mouse_distance()
        self.logger.debug(f"Dragging background by {distance} pixels")

    def _bg_mousedown(self, modifiers):
        if self.selection:
            self.selection = None
        self.logger.warning(f"Mouse down on background with modifiers {modifiers}")
        self.popup_manager.clear()
        return

    def _bg_mouseup(self, event, source, position, modifiers):
        current_time = js.Date.now()
        time_since_last_click = current_time - self.last_click_time
        potential_double_click = time_since_last_click < self.DBL_CLICK_THRESHOLD
        distance = self._mouse_distance()

        if distance < self.MIN_DRAG_DISTANCE:
            # Check if this is a double-click
            if potential_double_click:
                # Cancel pending single click
                if self.pending_click_timeout is not None:
                    js.clearTimeout(self.pending_click_timeout)
                    self.pending_click_timeout = None
                self._bg_dbl_click(event, source, position, modifiers)
                self.last_click_time = 0  # Reset to prevent triple-click
            else:
                # Delay single click to check for double-click
                if self.pending_click_timeout is not None:
                    js.clearTimeout(self.pending_click_timeout)

                self.pending_click_timeout = js.setTimeout(
                    create_proxy(
                        lambda: self._bg_click(event, source, position, modifiers)
                    ),
                    self.DBL_CLICK_THRESHOLD,
                )
                self.last_click_time = current_time

    # ---------------------
    # unit events
    # ---------------------

    def _unit_click(self, event, source, position, modifiers):
        self.logger.warning(source)
        if self.selection:
            self.selection = None
            self.logger.debug("Click processed, unit snapped to grid")
        else:
            self.logger.debug("Click with no selection")

        self.last_click_time = 0

    def _unit_dbl_click(self, event, source, position, modifiers):
        self.logger.debug("Double click detected")

        self.last_click_time = 0

        if Modifiers.ALT & modifiers:
            offset_pos = position[0] - 10, position[1] - 20

            self.popup_manager.create_popup(
                f"{self.selection.unit_id} @ {self.selection.position}", offset_pos
            )

    def _unit_drag(self, event, source, position, modifiers):
        self.board.constrain()
        self.board.hilite()

        distance = self._mouse_distance()
        if distance > self.MIN_DRAG_DISTANCE:
            # Place unit directly at cursor position
            self.selection.display.proxy.setAttribute(
                "transform", f"translate({self.drag_end[0]},{self.drag_end[1]})"
            )
            hex = self.canvas.hex_layout.pixel_to_hex(*self.drag_end)
            self.selection.enabled = hex in self.board.constraints

    def _unit_mousedown(self, unit, modifiers):
        # Only clear previous selection if clicking on a different unit
        if self.selection and self.selection != unit:
            self.selection = None

        self.selection = unit
        # this forced the unit to be on top of other units
        unit.display.proxy.parentElement.appendChild(unit.display.proxy)
        self.logger.debug(
            f"Mouse down on '{unit.unit_id}' @ {self.drag_start} with {modifiers}"
        )

    def _unit_mouseup(self, event, source, position, modifiers):
        try:
            current_time = js.Date.now()
            time_since_last_click = current_time - self.last_click_time
            potential_double_click = time_since_last_click < self.DBL_CLICK_THRESHOLD

            distance = self._mouse_distance()
            self._snap_to_grid()
            self.selection.enabled = True

            if distance < self.MIN_DRAG_DISTANCE:
                # Check if this is a double-click
                if potential_double_click:
                    # Cancel pending single click
                    if self.pending_click_timeout is not None:
                        js.clearTimeout(self.pending_click_timeout)
                        self.pending_click_timeout = None
                    self._unit_dbl_click(event, source, position, modifiers)
                    self.last_click_time = 0  # Reset to prevent triple-click
                else:
                    # Delay single click to check for double-click
                    
                    if self.pending_click_timeout is not None:
                        js.clearTimeout(self.pending_click_timeout)

                    self.pending_click_timeout = js.setTimeout(
                        create_proxy(
                            lambda: self._unit_click(event, source, position, modifiers)
                        ),
                        self.DBL_CLICK_THRESHOLD,
                    )
                    self.last_click_time = current_time
        finally:
            self.board.update(self.selection)
            self.selection = None
