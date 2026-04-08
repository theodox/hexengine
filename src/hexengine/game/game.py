from __future__ import annotations

import logging

from ..client import DisplayManager, UIState
from ..document import create_proxy, element, js
from ..map import Map
from ..state import ActionManager, GameState
from ..state.actions import NextPhase
from ..ui.popups import PopupManager
from .board import GameBoard
from .events import Hotkey, HotkeyHandlerMixin, Modifiers, MouseEventHandlerMixin
from .history import GameHistoryMixin
from .turn import Faction, Phase, TurnManager, TurnOrdering

# Screen-space pan per arrow key when zoomed in; Shift multiplies step.
_PAN_KEY_STEP = 48
_PAN_KEY_SHIFT_MULT = 3


class Game(MouseEventHandlerMixin, HotkeyHandlerMixin, GameHistoryMixin):
    """
    This is the main game class that ties together the board, turn manager, action manager, and display manager.

    The mixins are used to split the file into multiple files, not for reuses
    """

    def __init__(self) -> None:
        self.running = True
        container = element("map-container")
        map = element("map-canvas")
        terrain = element("map-terrain")
        svg = element("map-svg")
        units = element("map-units")
        action_button = element("advance-button")
        action_button.onclick = self.advance_turn
        self.popup_manager = PopupManager(container)

        assert map is not None, "Map canvas element not found"
        assert svg is not None, "Map SVG element not found"
        self.canvas = Map(container, map, terrain, svg, units)
        self.board = GameBoard(self.canvas)

        initial_state = GameState.create_empty(
            initial_faction="Blue", initial_phase="Movement"
        )
        self.action_mgr = ActionManager(initial_state)
        self.logger = logging.getLogger("game")
        self.logger.info(f"action_mgr created: {self.action_mgr}")

        self.ui_state = UIState()
        self.display_mgr = DisplayManager(self.canvas, self.board)

        # Connect display manager as observer to sync on state changes
        self.action_mgr.add_observer(self.display_mgr.sync_from_state)

        # TODO: Sync initial display from state once units are added via new system
        # self.display_mgr.sync_from_state(self.action_mgr.current_state)

        self.click_time = 0
        self.last_click_time = 0
        self.drag_start = (0, 0)
        self.drag_end = (0, 0)

        self.logger = logging.getLogger("game")
        self.logger.info("Game initialized")

        self.logger.info(
            f"[Game.__init__] Registering on_mouse_down: {self.on_mouse_down}"
        )
        self.canvas.on_mouse_down < self.on_mouse_down
        self.logger.info("[Game.__init__] Registered on_mouse_down")

        self.logger.info(f"[Game.__init__] Registering on_mouse_up: {self.on_mouse_up}")
        self.canvas.on_mouse_up < self.on_mouse_up
        self.logger.info("[Game.__init__] Registered on_mouse_up")

        self.logger.info(f"[Game.__init__] Registering on_drag: {self.on_drag}")
        self.canvas.on_drag < self.on_drag
        self.logger.info("[Game.__init__] Registered on_drag")

        self._register_hotkeys()

        self.turn_manager = TurnManager(
            factions=[Faction("Red"), Faction("Blue")],
            phases=[
                Phase("Movement", max_actions=2),
                Phase("Attack", max_actions=2),
            ],
            order=TurnOrdering.INTERLEAVED,
        )

        self.turn_manager.handlers.append(self.update_turn_display)

        # Register resize handler to refresh map on window resize/zoom
        js.window.addEventListener("resize", create_proxy(self._handle_resize))
        self.logger.info("Registered window resize handler")

        # Register zoom and pan handlers
        self._is_panning = False
        self._pan_start_x = 0
        self._pan_start_y = 0
        self._space_pressed = False

        container.addEventListener("wheel", create_proxy(self._handle_wheel), False)
        js.window.addEventListener("keydown", create_proxy(self._handle_keydown))
        js.window.addEventListener("keyup", create_proxy(self._handle_keyup))
        self.logger.info("Registered zoom and pan handlers")

    def update_turn_display(self, faction, phase) -> None:
        faction, phase = self.turn_manager.current
        actions = self.turn_manager.actions
        turn_info = f"{faction.name}-{phase.name} # {actions}"
        turn_bg = element("turn-display")
        turn_bg.classList.remove("red", "blue")
        turn_bg.classList.add(faction.name.lower())
        turn_info_element = element("turn-info")
        if turn_info_element:
            turn_info_element.innerText = turn_info

    def _handle_resize(self, event) -> None:
        """
        Handle window resize and zoom events.
        Refreshes the map canvas; pan/zoom are applied on layer roots, so unit
        transforms (map-space) stay valid.
        """
        self.logger.info("Window resized, refreshing map")
        self.canvas.refresh()
        if self.action_mgr is not None:
            self.display_mgr.redraw_terrain_overlay(self.action_mgr.current_state)

    def _handle_wheel(self, event) -> None:
        """
        Handle mouse wheel for zooming.
        """
        event.preventDefault()

        # Get mouse position relative to container
        rect = self.canvas._container.getBoundingClientRect()
        mouse_x = event.clientX - rect.left
        mouse_y = event.clientY - rect.top

        # Zoom in or out based on wheel delta
        zoom_speed = 0.001
        delta = -event.deltaY * zoom_speed

        self.canvas.adjust_zoom(delta, mouse_x, mouse_y)

    def _handle_keydown(self, event) -> None:
        """
        Handle keydown events for pan mode.
        """
        if event.key == " " or event.code == "Space":
            self._space_pressed = True
            # Change cursor to indicate pan mode
            self.canvas._container.style.cursor = "grab"

    def _handle_keyup(self, event) -> None:
        """
        Handle keyup events.
        """
        if event.key == " " or event.code == "Space":
            self._space_pressed = False
            self._is_panning = False
            # Restore cursor
            self.canvas._container.style.cursor = "default"

    # these are delegated to the board instance, but
    # exposed here for convenience
    @property
    def selection(self):
        return self.board.selection

    @property
    def layout(self):
        return self.canvas.hex_layout

    @selection.setter
    def selection(self, value):
        if self.board.selection:
            self.board.selection.hilited = False
        self.board.selection = value
        if self.board.selection:
            self.board.selection.hilited = True

    def add_unit(self, unit) -> None:
        self.board.add_unit(unit)

    def remove_unit(self, unit) -> None:
        self.board.remove_unit(unit)

    def pan_view(self, delta_x: float, delta_y: float) -> None:
        """Pan the map in screen pixels (CSS transform on layers; units stay in map space)."""
        self.canvas.adjust_pan(delta_x, delta_y)

    def on_key_down(self, event) -> None:
        key = event.key.lower()
        modifiers = Modifiers.from_event(event)
        if key in ("arrowleft", "arrowright", "arrowup", "arrowdown"):
            if self.canvas.zoom_level > 1.01:
                step = _PAN_KEY_STEP * (
                    _PAN_KEY_SHIFT_MULT if modifiers & Modifiers.SHIFT else 1
                )
                deltas = {
                    "arrowleft": (-step, 0),
                    "arrowright": (step, 0),
                    "arrowup": (0, -step),
                    "arrowdown": (0, step),
                }
                self.pan_view(*deltas[key])
                event.preventDefault()
                return
        HotkeyHandlerMixin.on_key_down(self, event)

    @Hotkey("delete", Modifiers.NONE)
    def delete_selected_unit(self) -> None:
        if self.ui_state.selected_unit_id:
            from ..state.actions import DeleteUnit

            action = DeleteUnit(self.ui_state.selected_unit_id)
            self.execute_action(action)

            # Clear UI state
            self.ui_state.end_drag()
            self.display_mgr.clear_highlights()

            self.logger.info(f"Deleted unit {self.ui_state.selected_unit_id}")
        else:
            self.logger.debug("No unit selected to delete")

    @Hotkey("enter", Modifiers.NONE)
    def popup_selected_unit_info(self) -> None:
        if self.selection:
            loc = self.layout.hex_to_pixel(self.selection.position)
            self.popup_manager.create_popup(
                f"{self.selection.unit_id} @ {self.selection.faction}", loc
            )
            self.logger.info(f"Showing info for unit {self.selection.unit_id}")
        else:
            self.popup_manager.clear()
            self.logger.debug("No unit selected to show info")

    @Hotkey("escape", Modifiers.NONE)
    def clear_selection(self) -> None:
        self.popup_manager.clear()

    @Hotkey("r", Modifiers.NONE)
    def reset_view(self) -> None:
        """Reset zoom and pan to default."""
        self.canvas.reset_view()
        self.logger.info("View reset to default")

    @Hotkey("t", Modifiers.NONE)
    def toggle_terrain_overlay(self) -> None:
        """Toggle terrain tint layer (console: ``set_terrain_overlay`` / ``terrain_overlay_visible()``)."""
        self.canvas.set_terrain_overlay_visible(
            not self.canvas.terrain_overlay_visible
        )

    # ===== STATE SYSTEM HELPERS =====

    def execute_action(self, action):
        """
        Execute an action using the ActionManager.
        This automatically triggers display sync via observer pattern.
        """
        self.action_mgr.execute(action)
        # Display automatically syncs, no manual update needed!

    def get_current_state(self):
        """Get current committed game state (immutable)."""
        return self.action_mgr.current_state

    def is_my_turn(self) -> bool:
        """Local / hotseat: always True. NetworkGame overrides."""
        return True

    def _clear_drag_and_highlights(self) -> None:
        """Clear local drag preview, selection, and hex highlights (no server action)."""
        if self.ui_state.drag_preview:
            preview = self.ui_state.end_drag()
            if preview and self.action_mgr and self.action_mgr.current_state:
                u = self.action_mgr.current_state.board.units.get(preview.unit_id)
                if u:
                    self.display_mgr.clear_preview(preview.unit_id, u.position)
        self.ui_state.select_unit(None)
        self.display_mgr.clear_highlights()

    def start_drag_preview(self, unit_id: str):
        """Start drag preview for a unit."""
        state = self.action_mgr.current_state
        unit_state = state.board.units.get(unit_id)
        if not unit_state:
            return

        self.ui_state.select_unit(unit_id)
        game_unit = self.board.get_unit(unit_id)
        if game_unit:
            self.selection = game_unit

        # Initialize drag preview with unit's current position
        pixel_pos = self.canvas.hex_layout.hex_to_pixel(unit_state.position)
        self.ui_state.start_drag(
            unit_id, unit_state.position, pixel_pos[0], pixel_pos[1]
        )

        # Compute valid moves from committed state
        from ..state.logic import compute_valid_moves

        valid_moves = compute_valid_moves(state, unit_id, movement_budget=4.0)
        self.ui_state.set_constraints(valid_moves)

        # Clear old highlights and show new ones
        self.display_mgr.clear_highlights()
        self.display_mgr.highlight_hexes(valid_moves)

    def update_drag_preview(self, pixel_x: float, pixel_y: float, target_hex):
        """Update drag preview position."""
        self.ui_state.update_drag(pixel_x, pixel_y, target_hex)

        if self.ui_state.drag_preview:
            # Log the actual zoom/pan values being used
            self.logger.debug(
                f"update_drag_preview: screen=({pixel_x:.1f},{pixel_y:.1f}), "
                f"zoom={self.canvas._zoom_level:.2f}, pan=({self.canvas._pan_x:.1f},{self.canvas._pan_y:.1f})"
            )

            self.display_mgr.show_preview(
                unit_id=self.ui_state.drag_preview.unit_id,
                pixel_x=pixel_x,
                pixel_y=pixel_y,
                is_valid=self.ui_state.drag_preview.is_valid,
            )

    def end_drag_preview(self) -> bool:
        """
        End drag preview and commit if valid.
        Returns True if move was committed, False otherwise.
        """
        preview = self.ui_state.end_drag()

        if not preview:
            return False

        # Clear preview visually
        state = self.action_mgr.current_state
        unit = state.board.units.get(preview.unit_id)
        if unit:
            self.display_mgr.clear_preview(preview.unit_id, unit.position)

        # Clear highlights
        self.display_mgr.clear_highlights()

        # Commit if valid
        if preview.is_valid and preview.potential_target:
            from ..state.actions import MoveUnit

            action = MoveUnit(
                unit_id=preview.unit_id,
                from_hex=preview.original_position,
                to_hex=preview.potential_target,
            )
            self.execute_action(action)
            return True

        return False

    def advance_turn(self, _) -> None:
        """Advance to the next turn phase."""

        # Get the current state to determine what the next phase should be
        current_state = self.action_mgr.current_state
        current_faction = current_state.turn.current_faction
        current_phase = current_state.turn.current_phase

        # Find current position in the phase sequence
        for i, (faction, phase) in enumerate(self.turn_manager.phases):
            if faction.name == current_faction and phase.name == current_phase:
                # Get the next phase in sequence
                next_index = (i + 1) % len(self.turn_manager.phases)
                next_faction, next_phase = self.turn_manager.phases[next_index]

                self.logger.info(
                    f"Advancing from {current_faction}-{current_phase} to {next_faction.name}-{next_phase.name}"
                )
                np = NextPhase(
                    new_faction=next_faction.name,
                    new_phase=next_phase.name,
                    max_actions=next_phase.max_actions,
                )
                self.logger.info(f"Executing NextPhase action: {np}")
                self._clear_drag_and_highlights()
                self.selection = None
                self.execute_action(np)
                return

        # this should not happen
        raise RuntimeError("Current phase not found in turn manager phases")
