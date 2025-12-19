import logging
from ..map import Map
from ..document import element

from .events import EventHandlerMixin, HotkeyHandlerMixin, MouseState
from .popups import PopupManager, Popup
from .board import GameBoard
from .moves import GameQueue

class Game(EventHandlerMixin, HotkeyHandlerMixin):
    def __init__(self):
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
        self.mouse_state = MouseState.UP

        self.logger = logging.getLogger("game")
        self.logger.info("Game initialized")

        self.canvas.on_mouse_down < self.on_mouse_down
        self.canvas.on_mouse_up < self.on_mouse_up
        self.canvas.on_drag < self.on_drag

        self.actions = GameQueue(self.board)  # to be set later
        self.register_hotkeys()

    # these are delegated to the board instance, but
    # exposed here for convenience
    @property
    def selection(self):
        return self.board.selection

    @selection.setter
    def selection(self, value):
        self.board.selection = value

    def add_unit(self, unit):
        self.board.add_unit(unit)

    def remove_unit(self, unit):
        self.board.remove_unit(unit)