from ...document import js, create_proxy
from ...hexes.types import Hex
from .handler import EventInfo, Modifiers
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...units.game import GameUnit


class TargetType(Enum):
    UNIT = "unit"
    BACKGROUND = "background"


class MouseEventHandlerMixin:
    """Mixin class providing mouse event handling functionality for the Game class."""

    MIN_DRAG_DISTANCE: int = 16  # pixels
    DBL_CLICK_THRESHOLD: int = 330  # milliseconds

    pending_click_timeout: Optional[int] = None
    hex_path: list[Hex] = []
    current_hex: Optional[Hex] = None
    drag_start: tuple[float, float] = (0, 0)
    drag_end: tuple[float, float] = (0, 0)

    def _event_unit(self, eventInfo: EventInfo) -> Optional["GameUnit"]:
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
        self.hex_path.clear()

        self.logger.warning(f"Mouse down : {eventInfo}")
        # pixels
        self.drag_start = (
            eventInfo.position
            if eventInfo.position
            else (eventInfo.event.offsetX, eventInfo.event.offsetY)
        )

        if not eventInfo.unit_id:
            self._bg_mousedown(eventInfo)
        else:
            self._unit_mousedown(eventInfo)

    def on_drag(self, eventInfo: EventInfo) -> None:
        if eventInfo.event.buttons != 1:
            return
        # Prevent default to stop text selection during drag
        eventInfo.event.preventDefault()
        self.drag_end = (
            eventInfo.position
            if eventInfo.position
            else (eventInfo.event.offsetX, eventInfo.event.offsetY)
        )

        if not self.ui_state.selected_unit_id:
            self._bg_drag(eventInfo)
        else:
            self._unit_drag(eventInfo)

    def on_mouse_up(self, eventInfo: EventInfo) -> None:
        self.drag_end = eventInfo.position

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
            else "Double click with no selection"
        )

        offset_pos = eventInfo.position[0] + 10, eventInfo.position[1] + 20
        self.popup_manager.create_popup(
            f"{self.selection.unit_id} @ {self.selection.faction}", offset_pos
        )
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

        # Update drag preview (visual only, state unchanged)
        self.update_drag_preview(
            pixel_x=eventInfo.position[0],
            pixel_y=eventInfo.position[1],
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
            return

        # Check faction from state
        state = self.action_mgr.current_state
        unit_state = state.board.units.get(unit_id)

        if not unit_state:
            return

        faction, phase = self.turn_manager.current
        if unit_state.faction != faction.name:
            self.logger.warning(
                f"Cannot select unit {unit_id} of faction {unit_state.faction} during {faction.name}'s turn"
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
        if not self.ui_state.selected_unit_id:
            return

        current_time = js.Date.now()
        time_since_last_click = current_time - self.last_click_time
        maybe_dbl_click = time_since_last_click < self.DBL_CLICK_THRESHOLD
        maybe_click = self._mouse_distance() < self.MIN_DRAG_DISTANCE

        try:
            # Handle double-click
            if maybe_click and maybe_dbl_click:
                if self.pending_click_timeout is not None:
                    js.clearTimeout(self.pending_click_timeout)
                    self.pending_click_timeout = None
                self._unit_dbl_click(eventInfo)
                self.last_click_time = 0
                # Clear preview without committing
                self.ui_state.end_drag()
                self.display_mgr.clear_highlights()
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
                return

            # Handle regular drag move
            move_committed = self.end_drag_preview()
            if not move_committed:
                self.logger.warning("Invalid move")

        finally:
            self.hex_path.clear()
