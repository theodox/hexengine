from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..hexes.types import Hex
from ..map import Map

if TYPE_CHECKING:
    from ..units.game import GameUnit


class GameBoard:
    def __init__(self, map: Map) -> None:
        self._board: dict[Hex, GameUnit] = {}  # Maps positions to board elements
        self._units: dict[str, GameUnit] = {}  # Maps unit IDs to units
        self._selection: GameUnit | None = None
        self._map: Map = map
        self.logger: logging.Logger = logging.getLogger("game.board")

    @property
    def selection(self) -> GameUnit | None:
        return self._selection

    @selection.setter
    def selection(self, value: GameUnit | None) -> None:
        if self._selection:
            self.selection.hilited = False

        self._selection = value
        if value:
            self.selection.hilited = True

    def occupied(self, position: Hex) -> bool:
        occupant = self._board.get(position, False)
        return bool(occupant)

    def update(self) -> None:
        """Rebuild position index from current unit positions."""
        self._board.clear()
        for unit in self._units.values():
            self._board[unit.position] = unit
        self.logger.debug(str(self._board))

    def add_unit(self, unit: GameUnit) -> None:
        if self.occupied(unit.position):
            raise ValueError("Position already occupied")
        self._board[unit.position] = unit
        self._units[unit.unit_id] = unit
        self._map.add_unit(unit)

    def get_unit(self, unit_id: str) -> GameUnit | None:
        return self._units.get(unit_id)

    def remove_unit(self, unit: GameUnit) -> None:
        if self._selection is unit:
            self.selection = None
        self._units.pop(unit.unit_id, None)
        if self._board.get(unit.position) is unit:
            del self._board[unit.position]
        try:
            self._map.unit_layer.remove_unit(unit)
        except ValueError:
            pass
