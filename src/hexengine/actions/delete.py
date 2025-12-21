from typing import TYPE_CHECKING

from .base import Action

if TYPE_CHECKING:
    from ..units.game import GameUnit
    from ..game.board import GameBoard


class DeleteUnit(Action):
    def __init__(self, unit: "GameUnit") -> None:
        self.unit = unit
        self.unit_enabled = unit.enabled

    def do(self, game_board: "GameBoard") -> None:
        # Implement the logic to delete the unit from the game board
        assert game_board.get_unit(self.unit.unit_id) is not None
        self.unit.visible = False
        game_board.update(self.unit)

    def undo(self, game_board: "GameBoard") -> None:
        assert game_board.get_unit(self.unit.unit_id) is not None
        self.unit.active = True
        game_board.update(self.unit)

    def __repr__(self) -> str:
        return f"<DELETE '{self.unit.unit_id}'>"
