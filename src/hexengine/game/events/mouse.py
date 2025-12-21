from ...document import js, create_proxy
from ...actions import Move
from ...hexes.types import Hex
from .handler import EventInfo, Modifiers
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...units.game import GameUnit


class TargetType(Enum):
    UNIT = "unit"
    BACKGROUND = "background"


class EventHandlerMixin:
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

    def _snap_to_grid(self) -> None:
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

    # core event handling -- these delegate to background/unit handlers
    def on_mouse_down(self, eventInfo: EventInfo) -> None:
        # Prevent default to stop text selection and default drag behavior
        eventInfo.event.preventDefault()
        self.hex_path.clear()

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
        if not self.selection:
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
        self.board.constrain()
        self.board.hilite()

        is_new_hex = len(self.hex_path) == 0 or eventInfo.hex != self.hex_path[-1]
        if is_new_hex and eventInfo.hex in self.board.constraints:
            self.hex_path.append(eventInfo.hex)

        distance = self._mouse_distance()
        if distance > self.MIN_DRAG_DISTANCE:
            # Place unit directly at cursor position
            self.selection.display_at(*eventInfo.position)
            self.selection.enabled = eventInfo.hex in self.board.constraints

    def _unit_mousedown(self, eventInfo: EventInfo) -> None:
        # Only clear previous selection if clicking on a different unit
        unit = self._event_unit(eventInfo)
        self.selection = unit
        self.hex_path.append(unit.position)
        # this forced the unit to be on top of other units
        unit.display.proxy.parentElement.appendChild(unit.display.proxy)

    def _unit_mouseup(self, eventInfo: EventInfo) -> None:
        current_time = js.Date.now()
        time_since_last_click = current_time - self.last_click_time
        maybe_dbl_click = time_since_last_click < self.DBL_CLICK_THRESHOLD
        maybe_click = self._mouse_distance() < self.MIN_DRAG_DISTANCE

        try:

            if maybe_click and maybe_dbl_click:
                # Cancel pending single click
                if self.pending_click_timeout is not None:
                    js.clearTimeout(self.pending_click_timeout)
                    self.pending_click_timeout = None
                self._unit_dbl_click(eventInfo)
                self.last_click_time = 0  # Reset to prevent triple-click
                return

            if maybe_click:
                # Delay single click to check for double-click
                if self.pending_click_timeout is not None:
                    js.clearTimeout(self.pending_click_timeout)

                self.pending_click_timeout = js.setTimeout(
                    create_proxy(lambda: self._unit_click(eventInfo)),
                    self.DBL_CLICK_THRESHOLD,
                )
                self.last_click_time = current_time
                return

            if len(self.hex_path) > 1 and eventInfo.modifiers & Modifiers.SHIFT:
                self.logger.warning(self.hex_path)
                for h in range(1, len(self.hex_path)):
                    start = self.hex_path[h - 1]
                    end = self.hex_path[h]
                    move = Move(self.selection.unit_id, start, end)
                    self.enqueue(move)
                    return
            else:
                if eventInfo.hex not in self.board.constraints:
                    self.logger.warning("Invalid move, snapping back to original position")
                    self.selection.position = self.selection.position
                    return
                move = Move(
                    self.selection.unit_id, self.selection.position, eventInfo.hex
                )
                self.enqueue(move)

        finally:
            self.selection.enabled = True
            self.board.clear_hilite()
            self.hex_path.clear()
            self.board.update(self.selection)
