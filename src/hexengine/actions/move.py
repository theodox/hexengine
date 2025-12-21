from typing import TYPE_CHECKING

from .base import Action

if TYPE_CHECKING:
    from ..hexes.types import Hex
    from ..game.board import GameBoard


class Move(Action):
    def __init__(self, unit: str, from_hex: "Hex", to_hex: "Hex") -> None:
        self.unit = unit
        self.from_hex = from_hex
        self.to_hex = to_hex

    def do(self, game_board: "GameBoard") -> None:
        # Implement the logic to move the unit on the game board
        game_board.get_unit(self.unit).position = self.to_hex
        game_board.update(self.unit)

    def undo(self, game_board: "GameBoard") -> None:
        # Implement the logic to undo the move on the game board
        game_board.get_unit(self.unit).position = self.from_hex
        game_board.update(self.unit)

    def __repr__(self) -> str:
        return f"<MOVE '{self.unit}', {self.from_hex} -> {self.to_hex}>"
