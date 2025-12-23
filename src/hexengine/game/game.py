import logging

from ..document import element
from ..map import Map
from ..ui.popups import PopupManager
from .board import GameBoard
from .events import EventHandlerMixin, HotkeyHandlerMixin, Hotkey, Modifiers
from .history import GameHistoryMixin
from .turn import TurnManager, Faction, Phase, TurnOrdering


class Game(EventHandlerMixin, HotkeyHandlerMixin, GameHistoryMixin):
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

        self.click_time = 0
        self.last_click_time = 0
        self.drag_start = (0, 0)
        self.drag_end = (0, 0)

        self.logger = logging.getLogger("game")
        self.logger.info("Game initialized")

        self.canvas.on_mouse_down < self.on_mouse_down
        self.canvas.on_mouse_up < self.on_mouse_up
        self.canvas.on_drag < self.on_drag

        self._init_history()
        self._register_hotkeys()

        self.turn_manager = TurnManager(
            factions=[Faction("Red"), Faction("Blue")],
            phases=[
                Phase("Movement", max_actions=2),
                Phase("Attack", max_actions=2),
            ], order=TurnOrdering.INTERLEAVED
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
        if self.selection:
            from hexengine.actions.delete import DeleteUnit

            action = DeleteUnit(self.selection)
            self.enqueue(action)
            self.selection = None
            self.logger.info(f"Deleted unit {action.unit.unit_id}")
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
