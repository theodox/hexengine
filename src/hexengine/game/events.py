from asyncio.log import logger
import logging
from enum import Enum
import js
from pyodide.ffi import create_proxy
from ..dev_console import set_status
from ..hexes.shapes import radius


class MouseState(Enum):
    UP = 0
    DOWN = 1
    DRAGGING = 2


class MODIFIER_KEYS(Enum):
    ALT = "Alt"
    SHIFT = "Shift"
    CONTROL = "Control"

class TargetType(Enum):
    UNIT = "unit"
    BACKGROUND = "background"

class EventHandlerMixin:
    """Mixin class providing mouse event handling functionality for the Game class."""

    MIN_DRAG_DISTANCE = 10
    DBL_CLICK_THRESHOLD = 300  # milliseconds

    def get_modifier_keys(self, event):
        return {
            MODIFIER_KEYS.ALT: event.getModifierState("Alt"),
            MODIFIER_KEYS.SHIFT: event.getModifierState("Shift"),
            MODIFIER_KEYS.CONTROL: event.getModifierState("Control"),
        }
    
    def get_target(self, event):
        target = event.target

        if target.id == "map-units":
            return TargetType.BACKGROUND, None
            
        unit_id = None
        while target and not unit_id:
            unit_id = target.getAttribute("data-unit")
            target = target.parentElement
        unit = self.canvas.units.get_unit(unit_id)
        assert unit, f"Failed to find clickable unit"
        return TargetType.UNIT, unit

    def on_mouse_down(self, event, source, position):
        # Prevent default to stop text selection and default drag behavior
        event.preventDefault()
        modifiers = self.get_modifier_keys(event)

        # position contains the properly calculated coordinates from Handler
        self.drag_start = position if position else (event.offsetX, event.offsetY)
        self.mouse_state = MouseState.DOWN

        target_type, unit = self.get_target(event)
        set_status(f"Target: {unit} {self.mouse_state} {self.selection}")
        # Walk up the tree to find element with data-unit
        if target_type == TargetType.BACKGROUND:
            self._bg_mousedown(modifiers)
        else:   
            self._unit_mousedown(unit, modifiers)


    def on_drag(self, event, source, position):
        if event.buttons != 1:
            self.mouse_state = MouseState.UP
            return        

        # Prevent default to stop text selection during drag
        event.preventDefault()

        self.drag_end = position if position else (event.offsetX, event.offsetY)
        self.mouse_state = MouseState.DRAGGING

        if not self.selection:
            self._bg_drag(event, source, position)
        else:
            self._unit_drag(event, source, position)
      

    def on_mouse_up(self, *args):
        logger.warning(args)
        self.mouse_state = MouseState.UP
        event, source, position = args
        if event.getModifierState("Alt"):
            self._on_alt_mouse_up(event, source, position)
        elif event.getModifierState("Shift"):
            self._on_shift_mouse_up(event, source, position)
        elif event.getModifierState("Control"):
            self._on_control_mouse_up(event, source, position)
        else:
            self._on_mouse_up(event, source, position)

    def _on_alt_mouse_up(self, event, source, position):
        logger.warning("Alt key pressed, skipping snap to grid")
        self._on_mouse_up(event, source, position)

    def _on_shift_mouse_up(self, event, source, position):
        logger.warning("Shift key pressed, skipping snap to grid")
        self._on_mouse_up(event, source, position)

    def _on_control_mouse_up(self, event, source, position):
        logger.warning("Control key pressed, skipping snap to grid")
        self._on_mouse_up(event, source, position)

    def _on_mouse_up(self, event, source, position):
        target = event.target
        set_status(f"Target: {target} {self.mouse_state} {self.selection}")

        target_type, unit = self.get_target(event)

        logger.warning(f"Mouse up on {target_type} {unit}")

        self.drag_end = position
        
        if target_type == TargetType.BACKGROUND:
            self._bg_mouseup(event, source, position)
        else:
            self._unit_mouseup(event, source, position)

    def _bg_mouseup(self, event, source, position):
        current_time = js.Date.now()            
        time_since_last_click = current_time - self.last_click_time
        potential_double_click = time_since_last_click < self.DBL_CLICK_THRESHOLD
        distance = self.mouse_distance()

        if distance < self.MIN_DRAG_DISTANCE:
        # Check if this is a double-click
            if potential_double_click:
                # Cancel pending single click
                if self.pending_click_timeout is not None:
                    js.clearTimeout(self.pending_click_timeout)
                    self.pending_click_timeout = None
                self.logger.debug(f"Double-click detected ({time_since_last_click} ms)")
                self._on_bg_dbl_click(event, source, position)
                self.last_click_time = 0  # Reset to prevent triple-click
            else:
                # Delay single click to check for double-click
                self.logger.debug(f"Click detected, waiting for potential double-click")
                if self.pending_click_timeout is not None:
                    js.clearTimeout(self.pending_click_timeout)

                self.pending_click_timeout = js.setTimeout(
                    create_proxy(lambda: self._on_bg_click(event, source, position)),
                    self.double_click_threshold,
                )
                self.last_click_time = current_time

    def _unit_mouseup(self, event, source, position):
        if not self.selection:
            self.logger.warning("Unit mouse up with no selection")
            return

        current_time = js.Date.now()            
        time_since_last_click = current_time - self.last_click_time
        potential_double_click = time_since_last_click < self.DBL_CLICK_THRESHOLD

        distance = self.mouse_distance()
        self.snap_to_grid()
        
        if distance < self.MIN_DRAG_DISTANCE:
            # Check if this is a double-click
            if potential_double_click:
                # Cancel pending single click
                if self.pending_click_timeout is not None:
                    js.clearTimeout(self.pending_click_timeout)
                    self.pending_click_timeout = None
                self.logger.debug(f"Double-click detected ({time_since_last_click} ms)")
                self._on_dbl_click_unit(event, source, position)
                self.last_click_time = 0  # Reset to prevent triple-click
            else:
                # Delay single click to check for double-click
                self.logger.debug(f"Click detected, waiting for potential double-click")
                if self.pending_click_timeout is not None:
                    js.clearTimeout(self.pending_click_timeout)

                self.pending_click_timeout = js.setTimeout(
                    create_proxy(lambda: self._on_unit_click(event, source, position)),
                    self.double_click_threshold,
                )
                self.last_click_time = current_time
      

    def _on_bg_click(self, event, source, position):
        self.logger.debug("Click on background")
        if self.selection:
            self.selection.active = False
            self.selection = None
        self.last_click_time = 0

    def _on_bg_dbl_click(self, event, source, position):
        self.logger.debug("Double click on background")
        if self.selection:
            self.selection.active = False
            self.selection = None
            self.logger.debug("Double click processed, unit snapped to grid")
        else:
            self.logger.debug("Double click with no selection")
        self.last_click_time = 0
        
    def _bg_click(self, event, source, position):
        self.logger.debug("Click on background")
        # Example: create a new unit at the clicked position
        # new_unit = self.canvas.units.create_unit(position)
        # self.canvas.add_unit(new_unit)
        self.selection = None
        self.popup_manager.clear()

    def _on_unit_click(self, event, source, position):
        logger.warning(source)
        if self.selection:
            self.selection.active = False
            self.selection = None
            self.logger.debug("Click processed, unit snapped to grid")
        else:
            self.logger.debug("Click with no selection")

        self.last_click_time = 0


    def _on_dbl_click_unit(self, event, source, position):
       
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

        if self.get_modifier_keys(event)[MODIFIER_KEYS.ALT]:
            self.popup_manager.create_popup("unit", position)
       
    def _unit_mousedown(self, unit, modifiers):
        # Only clear previous selection if clicking on a different unit
        if self.selection and self.selection != unit:
            self.selection.active = False
        unit.active = True
        self.selection = unit
        self.logger.debug(
            f"Mouse down on unit {unit.unit_id} at position {self.drag_start} with modifiers {modifiers}"
            )
        
    def _bg_mousedown(self, modifiers):
        if self.selection:
            self.selection.active = False
        self.selection = None
        self.logger.warning(f"Mouse down on background with modifiers {modifiers}")
        self.popup_manager.clear()
        return
    

    def _bg_drag(self, event, source, position):
        distance = self.mouse_distance()
        self.logger.debug(f"Dragging background by {distance} pixels")

    def _unit_drag(self, event, source, position):
        distance = self.mouse_distance()
        if distance > 12:
            # Place unit directly at cursor position
            self.selection.display.proxy.setAttribute(
                "transform", f"translate({self.drag_end[0]},{self.drag_end[1]})"
            )
