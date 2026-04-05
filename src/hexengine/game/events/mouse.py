from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from ...document import create_proxy, js, jsnull
from ...hexes.types import Hex
from .handler import EventInfo, Modifiers

if TYPE_CHECKING:
    from ...units.game import GameUnit


class TargetType(Enum):
    UNIT = "unit"
    BACKGROUND = "background"


class MouseEventHandlerMixin:
    """Mixin class providing mouse event handling functionality for the Game class."""

    MIN_DRAG_DISTANCE: int = 16  # pixels
    DBL_CLICK_THRESHOLD: int = 330  # milliseconds

    pending_click_timeout: int | None = None
    hex_path: list[Hex] = []
    current_hex: Hex | None = None
    drag_start: tuple[float, float] = (0, 0)
    drag_end: tuple[float, float] = (0, 0)

    def _event_unit(self, eventInfo: EventInfo) -> GameUnit | None:
        if eventInfo.unit_id is None:
            return None
        return self.board.get_unit(eventInfo.unit_id)

    # utilities
    def _mouse_distance(self) -> float:
        dx = abs(self.drag_start[0] - self.drag_end[0])
        dy = abs(self.drag_start[1] - self.drag_end[1])
        return (dx**2 + dy**2) ** 0.5

    # core event handling -- these delegate to background/unit handlers
    def on_mouse_down(self, eventInfo: EventInfo) -> None:
        # Prevent default to stop text selection and default drag behavior
        eventInfo.event.preventDefault()

        # Check if we're in pan mode (space key held or middle mouse button)
        if self._space_pressed or eventInfo.event.button == 1:  # Middle mouse button
            self._is_panning = True
            self._pan_start_x = eventInfo.event.clientX
            self._pan_start_y = eventInfo.event.clientY
            self.canvas._container.style.cursor = "grabbing"
            return

        self.hex_path.clear()

        self.logger.debug(f"Mouse down : {eventInfo}")
        # pixels - use raw_position for screen-space distance calculations
        self.drag_start = (
            eventInfo.raw_position
            if eventInfo.raw_position
            else (eventInfo.event.offsetX, eventInfo.event.offsetY)
        )

        if eventInfo.unit_id == jsnull or eventInfo.unit_id is None:
            self._bg_mousedown(eventInfo)
        else:
            self._unit_mousedown(eventInfo)

    def on_drag(self, eventInfo: EventInfo) -> None:
        # Handle panning mode
        if self._is_panning:
            delta_x = eventInfo.event.clientX - self._pan_start_x
            delta_y = eventInfo.event.clientY - self._pan_start_y
            self.pan_view(delta_x, delta_y)
            self._pan_start_x = eventInfo.event.clientX
            self._pan_start_y = eventInfo.event.clientY
            return

        if eventInfo.event.buttons != 1:
            return
        # Prevent default to stop text selection during drag
        eventInfo.event.preventDefault()
        self.drag_end = (
            eventInfo.raw_position
            if eventInfo.raw_position
            else (eventInfo.event.offsetX, eventInfo.event.offsetY)
        )

        if not self.ui_state.selected_unit_id:
            self._bg_drag(eventInfo)
        elif not self.is_my_turn():
            return
        else:
            self._unit_drag(eventInfo)

    def on_mouse_up(self, eventInfo: EventInfo) -> None:
        # Handle end of panning
        if self._is_panning:
            self._is_panning = False
            if self._space_pressed:
                self.canvas._container.style.cursor = "grab"
            else:
                self.canvas._container.style.cursor = "default"
            return

        self.drag_end = eventInfo.raw_position

        if not eventInfo.unit_id:
            self._bg_mouseup(eventInfo)
        else:
            self._unit_mouseup(eventInfo)

    # ---------------------
    # background events
    # ---------------------

    def _bg_click(self, eventInfo: EventInfo) -> None:
        self.logger.debug("Click on background")
        self.selection = None
        self.last_click_time = 0

    def _bg_dbl_click(self, eventInfo: EventInfo) -> None:
        self.logger.debug("Double click on background")
        if self.selection:
            self.selection = None
            self.logger.debug("Double click processed, unit snapped to grid")
        else:
            self.logger.debug("Double click with no selection")
        self.last_click_time = 0

    def _bg_drag(self, eventInfo: EventInfo) -> None:
        distance = self._mouse_distance()
        self.current_hex = eventInfo.hex

        is_path = eventInfo.modifiers & Modifiers.SHIFT
        is_new_hex = len(self.hex_path) == 0 or eventInfo.hex != self.hex_path[-1]
        if is_path and is_new_hex:
            self.hex_path.append(eventInfo.hex)
        self.logger.debug(f"Dragging background by {distance} pixels")

    def _bg_mousedown(self, eventInfo: EventInfo) -> None:
        self.selection = None
        self.logger.warning(
            f"Mouse down on background with modifiers {eventInfo.modifiers}"
        )
        self.popup_manager.clear()
        return

    def _bg_mouseup(self, eventInfo: EventInfo) -> None:
        current_time = js.Date.now()
        time_since_last_click = current_time - self.last_click_time
        potential_click = self._mouse_distance() < self.MIN_DRAG_DISTANCE
        potential_double_click = time_since_last_click < self.DBL_CLICK_THRESHOLD

        if potential_click:
            if potential_double_click:
                # Cancel pending single click
                if self.pending_click_timeout is not None:
                    js.clearTimeout(self.pending_click_timeout)
                    self.pending_click_timeout = None
                self._bg_dbl_click(eventInfo)
                self.last_click_time = 0  # Reset to prevent triple-click
            else:
                # Delay single click to check for double-click
                if self.pending_click_timeout is not None:
                    js.clearTimeout(self.pending_click_timeout)

                self.pending_click_timeout = js.setTimeout(
                    create_proxy(lambda: self._bg_click(eventInfo)),
                    self.DBL_CLICK_THRESHOLD,
                )
                self.last_click_time = current_time

    # ---------------------
    # unit events
    # ---------------------

    def _unit_click(self, eventInfo: EventInfo) -> None:
        unit = self._event_unit(eventInfo)
        self.logger.debug(
            f"Click on {unit.unit_id}" if unit else "Click with no selection"
        )
        self.last_click_time = 0
        self.selection = unit

    def _unit_dbl_click(self, eventInfo: EventInfo) -> None:
        unit = self._event_unit(eventInfo)
        self.logger.debug(
            f"Double click on {unit.unit_id}"
            if unit
            else "Double click with no unit under cursor"
        )

        offset_pos = eventInfo.raw_position[0] + 10, eventInfo.raw_position[1] + 20
        if not unit or not eventInfo.unit_id:
            self.last_click_time = 0
            return

        # Use server/board state for faction; GameUnit.faction may be a class default.
        faction = unit.faction
        if self.action_mgr and self.action_mgr.current_state:
            us = self.action_mgr.current_state.board.units.get(eventInfo.unit_id)
            if us is not None:
                faction = us.faction

        self.popup_manager.create_popup(f"{unit.unit_id} @ {faction}", offset_pos)
        self.last_click_time = 0

    def _unit_drag(self, eventInfo: EventInfo) -> None:
        """
        Drag handler using immutable state system.

        Key features:
        - Reads constraints from committed state (no mutation)
        - Updates preview via DisplayManager (no direct unit manipulation)
        - Game state unchanged until mouseup
        """
        if not self.ui_state.selected_unit_id:
            return

        if not self.is_my_turn():
            return

        state = self.action_mgr.current_state
        if state is None:
            return
        su = state.board.units.get(self.ui_state.selected_unit_id)
        if su is None or su.faction != state.turn.current_faction:
            return

        # Get current zoom/pan values
        zoom = self.canvas._zoom_level
        pan_x = self.canvas._pan_x
        pan_y = self.canvas._pan_y

        # Get both raw and map-space positions for comparison
        raw_x, raw_y = eventInfo.raw_position
        map_x, map_y = eventInfo.position

        # Calculate what map position SHOULD be from raw position
        expected_map_x = (raw_x - pan_x) / zoom
        expected_map_y = (raw_y - pan_y) / zoom

        self.logger.debug(
            f"_unit_drag: raw=({raw_x:.1f},{raw_y:.1f}), "
            f"map=({map_x:.1f},{map_y:.1f}), "
            f"expected_map=({expected_map_x:.1f},{expected_map_y:.1f}), "
            f"zoom={zoom:.2f}, pan=({pan_x:.1f},{pan_y:.1f}), hex={eventInfo.hex}"
        )

        # Use the map-space coordinates from eventInfo (already inverse-transformed)
        self.update_drag_preview(
            pixel_x=map_x,
            pixel_y=map_y,
            target_hex=eventInfo.hex,
        )

        # Track path for shift-dragging
        is_new_hex = len(self.hex_path) == 0 or eventInfo.hex != self.hex_path[-1]
        if (
            is_new_hex
            and self.ui_state.drag_preview
            and self.ui_state.drag_preview.is_valid
        ):
            self.hex_path.append(eventInfo.hex)

    def _unit_mousedown(self, eventInfo: EventInfo) -> None:
        """
        Mousedown handler using immutable state system.

        Key features:
        - Checks state instead of GameUnit objects
        - Starts drag preview via ui_state
        """
        unit_id = eventInfo.unit_id
        if not unit_id:
            self.logger.error("No unit_id on unit mousedown")
            return

        # Check action manager is initialized
        if self.action_mgr is None:
            self.logger.error("action_mgr is None - game not fully initialized")
            return

        # Check faction from state
        state = self.action_mgr.current_state
        if state is None:
            self.logger.error("current_state is None - game not fully initialized")
            return

        self.logger.info(
            f"State has {len(state.board.units)} units: {list(state.board.units.keys())}"
        )
        unit_state = state.board.units.get(unit_id)

        self.logger.warning(f"Mouse down state {unit_state} for unit {unit_id}")
        if not unit_state:
            return

        if not self.is_my_turn():
            self._clear_drag_and_highlights()
            self.logger.debug("Ignoring unit mousedown: not this client's turn")
            return

        # Check if it's the right faction's turn (use server state, not local TurnManager)
        current_faction = state.turn.current_faction
        if unit_state.faction != current_faction:
            self._clear_drag_and_highlights()
            self.logger.warning(
                f"Cannot select unit {unit_id} of faction {unit_state.faction} during {current_faction}'s turn"
            )
            return

        # Start drag preview
        self.start_drag_preview(unit_id)
        self.hex_path.clear()
        self.hex_path.append(unit_state.position)

        # Move display to top (still needs DOM manipulation)
        display = self.display_mgr.get_display(unit_id)
        if display:
            display.proxy.parentElement.appendChild(display.proxy)

    def _unit_mouseup(self, eventInfo: EventInfo) -> None:
        """
        Mouseup handler using immutable state system.

        Key features:
        - Commits move via ActionManager (only mutation point)
        - Preview cleared automatically
        - State unchanged if move is invalid
        """
        current_time = js.Date.now()
        time_since_last_click = current_time - self.last_click_time
        maybe_dbl_click = time_since_last_click < self.DBL_CLICK_THRESHOLD
        maybe_click = self._mouse_distance() < self.MIN_DRAG_DISTANCE

        try:
            # Double-click (e.g. inspect): only when no active drag-preview. If the user
            # started a unit drag, drag_preview is set even for tiny motion; without this,
            # a second quick release can look like a double-click and fight drag/end_drag.
            if maybe_click and maybe_dbl_click and self.ui_state.drag_preview is None:
                if self.pending_click_timeout is not None:
                    js.clearTimeout(self.pending_click_timeout)
                    self.pending_click_timeout = None
                self._unit_dbl_click(eventInfo)
                self.last_click_time = 0
                if self.ui_state.selected_unit_id:
                    self.ui_state.end_drag()
                    self.display_mgr.clear_highlights()
                return

            if not self.is_my_turn():
                self._clear_drag_and_highlights()
                if not self.ui_state.selected_unit_id and maybe_click:
                    self.last_click_time = current_time
                return

            if not self.ui_state.selected_unit_id:
                # Record click time so a second click-up on a unit can register as
                # double-click (e.g. inspect enemy). Otherwise last_click_time stays 0
                # and time_since_last_click is never within DBL_CLICK_THRESHOLD.
                if maybe_click:
                    self.last_click_time = current_time
                return

            # Handle single click (delayed to detect double-click)
            if maybe_click:
                if self.pending_click_timeout is not None:
                    js.clearTimeout(self.pending_click_timeout)

                self.pending_click_timeout = js.setTimeout(
                    create_proxy(lambda: self._unit_click(eventInfo)),
                    self.DBL_CLICK_THRESHOLD,
                )
                self.last_click_time = current_time
                # Clear preview without committing
                self.ui_state.end_drag()
                self.display_mgr.clear_highlights()
                return

            # Handle multi-hex path (shift-drag)
            if len(self.hex_path) > 1 and eventInfo.modifiers & Modifiers.SHIFT:
                self.logger.warning(self.hex_path)
                from ...state.actions import MoveUnit

                unit_id = self.ui_state.selected_unit_id

                for h in range(1, len(self.hex_path)):
                    start = self.hex_path[h - 1]
                    end = self.hex_path[h]
                    action = MoveUnit(unit_id, start, end)
                    self.execute_action(action)

                self.ui_state.end_drag()
                self.display_mgr.clear_highlights()
                self.last_click_time = 0
                return

            # Handle regular drag move
            move_committed = self.end_drag_preview()
            if not move_committed:
                self.logger.warning("Invalid move")
            # Avoid pairing this release with the next click as a double-click
            self.last_click_time = 0

        finally:
            self.hex_path.clear()
