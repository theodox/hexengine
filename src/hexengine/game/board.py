from typing import Optional
import heapq
import logging

from ..hexes.math import neighbors
from ..hexes.types import Hex
from ..map import Map


class GameBoard:
    def __init__(self, map: Map) -> None:
        self._board = dict()  # Maps positions to board elements
        self._units = dict()  # Maps unit IDs to units
        self._selection = None
        self._map = map
        self._constraints = set()
        self._hilited = False
        self._locations = {}  # maps positions to movement costs
        self.logger = logging.getLogger("game.board")

    @property
    def selection(self):
        return self._selection

    @selection.setter
    def selection(self, value):
        if self._selection:
            self.selection.hilited = False

        self._selection = value
        if value:
            self.selection.hilited = True
            self.constrain()
        else:
            self.clear_hilite()

    def add_location(self, location) -> None:
        self._locations[location.position] = location

    def get_location_cost(self, position: Hex) -> float:
        # returns movement cost for the given position
        location = self._locations.get(position)
        if location is None:
            return 1.0
        return location.movement_cost

    def occupied(self, position: Hex) -> bool:
        occupant = self._board.get(position, False)
        return bool(occupant)

    def impassable(self, position: Hex) -> bool:
        return self.get_location_cost(position) == float("inf")

    def constrain(self, movement_budget: int = 4) -> set[Hex]:
        self._constraints.clear()
        for s in self.reachable_hexes(self.selection.position, movement_budget):
            if not self.occupied(s) and not self.impassable(s):
                self._constraints.add(s)
        return self._constraints

    @property
    def constraints(self):
        return self._constraints

    def hilite(self) -> None:
        if not self._hilited:
            self._map.draw_hexes(self._constraints)
            self._hilited = True

    def clear_hilite(self) -> None:
        if self._hilited:
            self._map.svg_layer.clear()
            self.logger.debug("clearing constraints")
        self._hilited = False

    def clear_constraints(self) -> None:
        self._map.svg_layer.clear()
        self._constraints = set()

    def update(self, item) -> None:
        """move the item to its current position"""
        self._board.clear()
        for item in self._units.values():
            self._board[item.position] = item
        self.logger.debug(str(self._board))

    def add_unit(self, unit) -> None:
        if self.occupied(unit.position):
            raise ValueError("Position already occupied")
        self._board[unit.position] = unit
        self._units[unit.unit_id] = unit
        self._map.add_unit(unit)

    def get_unit(self, unit_id: str):
        return self._units.get(unit_id)

    def reachable_hexes(self, start_hex: Hex, max_cost: float) -> dict[Hex, float]:
        """
        Calculate all hexes reachable from start_hex within max_cost.

        Args:
            start_hex: The starting hex position (Hex object)
            max_cost: Maximum movement cost allowed

        Returns:
            dict: Maps hex positions to their accumulated movement cost from start_hex
                  Only includes hexes reachable at or below max_cost
        """
        # Dictionary to store the minimum cost to reach each hex
        costs = {start_hex: 0}

        # Priority queue: (cost, counter, hex)
        # Counter is used as a tie-breaker to avoid comparing hex objects
        # Using a heap to always process the lowest cost hex first
        counter = 0
        heap = [(0, counter, start_hex)]

        while heap:
            current_cost, _, current_hex = heapq.heappop(heap)

            # Skip if we've already found a better path to this hex
            if current_cost > costs.get(current_hex, float("inf")):
                continue

            # Explore all neighboring hexes
            for neighbor in neighbors(current_hex):
                # Calculate cost to move to this neighbor
                neighbor_terrain_cost = self.get_location_cost(neighbor)
                new_cost = current_cost + neighbor_terrain_cost

                # Only process if within budget and not occupied
                if new_cost <= max_cost and not self.occupied(neighbor):
                    # If this is a better path to the neighbor, update it
                    if new_cost < costs.get(neighbor, float("inf")):
                        costs[neighbor] = new_cost
                        counter += 1
                        heapq.heappush(heap, (new_cost, counter, neighbor))

        return costs
