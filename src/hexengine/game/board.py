from ..hexes.shapes import radius
from ..map import Map
import logging
import js.eval as js_eval




class GameBoard:
    def __init__(self, map: Map):
        self._board = dict()  # Maps positions to board elements
        self._units = dict()  # Maps unit IDs to units
        self._selection = None
        self._map = map
        self._constraints = {}
        self._hilited = False
        self._locations = {}  # maps positions to movement costs
        
    @property
    def selection(self):
        return self._selection

    @selection.setter
    def selection(self, value):
        if self._selection:
            self.selection.active = False

        self._selection = value
        if value:
            self.selection.active = True
            self.constrain()
        else:
            self.clear_hilite()

    def add_location(self, location):
        self._locations[location.position] = location

    def get_location_cost(self, position):
        # returns movement cost for the given position
        location = self._locations.get(position)
        if location is None:
            return 1.0
        return location.movement_cost

    def occupied(self, position):
        occupant = self._board.get(position)
        return occupant is not None

    def constrain(self):
        if self.selection is None:
            return set()
        legit = radius(self.selection.position, 4)
        const = {s for s in legit if not self.occupied(s) and  s not in self._locations}

        self._constraints = const
        return self._constraints

    def hilite(self):
        if not self._hilited:
            self._map.draw_hexes(self._constraints)
            self._hilited = True

    def clear_hilite(self):
        if self._hilited:
            self._map.svg_layer.clear()
            logging.getLogger("game").debug("clearing constraints")
        self._hilited = False

    def clear_constraints(self):
        self._map.svg_layer.clear()
        self._constraints = set()

    def update(self, item):
        """move the item to its current position"""
        self._board.clear()
        for item in self._units.values():
            self._board[item.position] = item 
        logging.getLogger("game").debug(str(self._board))

    def add_unit(self, unit):
        if self.occupied(unit.position):
            raise ValueError("Position already occupied")
        self._board[unit.position] = unit
        self._units[unit.unit_id] = unit
        self._map.add_unit(unit)
       

    def get_unit(self, unit_id):
        return self._units.get(unit_id)

