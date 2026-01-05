import logging

from ..document import element
from ..map import Map
from ..ui.popups import PopupManager
from .board import GameBoard
from .events import MouseEventHandlerMixin, HotkeyHandlerMixin, Hotkey, Modifiers
from .history import GameHistoryMixin
from .turn import TurnManager, Faction, Phase, TurnOrdering

# New state system imports
from ..state import GameState, ActionManager
from ..client import UIState, DisplayManager


class Game(MouseEventHandlerMixin, HotkeyHandlerMixin, GameHistoryMixin):
    def __init__(self) -> None:
        self.running = True
        container = element("map-container")
        map = element("map-canvas")
        svg = element("map-svg")
        units = element("map-units")
        self.popup_manager = PopupManager(container)

        assert map is not None, "Map canvas element not found"
        assert svg is not None, "Map SVG element not found"
        self.canvas = Map(container, map, svg, units)
        self.board = GameBoard(self.canvas)

        initial_state = GameState.create_empty(
            initial_faction="Blue", initial_phase="Movement"
        )
        self.action_mgr = ActionManager(initial_state)
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

        from ..document import js
        self.logger.info(f"[Game.__init__] Registering on_mouse_down: {self.on_mouse_down}")
        self.canvas.on_mouse_down < self.on_mouse_down
        self.logger.info(f"[Game.__init__] Registered on_mouse_down")
        
        self.logger.info(f"[Game.__init__] Registering on_mouse_up: {self.on_mouse_up}")
        self.canvas.on_mouse_up < self.on_mouse_up
        self.logger.info(f"[Game.__init__] Registered on_mouse_up")

        self.logger.info(f"[Game.__init__] Registering on_drag: {self.on_drag}")    
        self.canvas.on_drag < self.on_drag
        self.logger.info(f"[Game.__init__] Registered on_drag")

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

    def update_turn_display(self, faction, phase) -> None:
        faction, phase = self.turn_manager.current
        actions = self.turn_manager.actions
        turn_info = f"{faction.name}-{phase.name} # {actions})"
        turn_bg = element("turn-display")
        turn_bg.classList.remove("red", "blue")
        turn_bg.classList.add(faction.name.lower())
        turn_info_element = element("turn-info")
        if turn_info_element:
            turn_info_element.innerText = turn_info

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
        self.popup_manager.clear()
        if self.selection:
            loc = self.layout.hex_to_pixel(self.selection.position)
            self.popup_manager.create_popup(
                f"{self.selection.unit_id} @ {self.selection.faction}", loc
            )
            self.logger.info(f"Showing info for unit {self.selection.unit_id}")
        else:
            self.logger.debug("No unit selected to show info")

    @Hotkey("escape", Modifiers.NONE)
    def clear_selection(self) -> None:
        self.popup_manager.clear()

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

    def start_drag_preview(self, unit_id: str):
        """Start drag preview for a unit."""
        self.ui_state.select_unit(unit_id)

        # Compute valid moves from committed state
        from ..state.logic import compute_valid_moves

        state = self.action_mgr.current_state
        valid_moves = compute_valid_moves(state, unit_id, movement_budget=4.0)
        self.ui_state.set_constraints(valid_moves)

        # Highlight valid move hexes
        self.display_mgr.highlight_hexes(valid_moves)

    def update_drag_preview(self, pixel_x: float, pixel_y: float, target_hex):
        """Update drag preview position."""
        self.ui_state.update_drag(pixel_x, pixel_y, target_hex)

        if self.ui_state.drag_preview:
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
