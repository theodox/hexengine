from ..hexes.shapes import radius
from ..map import Map


class GameBoard:

    def __init__(self, map: Map):
        self.board = {}  # Maps positions to board elements
        self._selection = None
        self.map = map
        self._constraints = {}

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
            self.map.clear()
     

    def occupied(self, position):
        occupant = self.board.get(position)
        return (occupant is not None) or (occupant == self.selection)

    def constrain(self):
        if self.selection is None:
            return set()
        legit = radius(self.selection.position, 4)
        const = {
            s for s in legit if not self.occupied(s)
        }
        self._constraints = const
        return self._constraints
    
    def highlight(self):
        self.map.draw_hexes(self._constraints, "blue")

    

        