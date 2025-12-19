from asyncio.log import logger
from typing import Protocol
import logging


class Action(Protocol):
    def do(self, game_board): ...

    def undo(self, game_board): ...


class Move(Action):
    def __init__(self, unit, from_hex, to_hex):
        self.unit = unit
        self.from_hex = from_hex
        self.to_hex = to_hex

    def do(self, game_board):
        # Implement the logic to move the unit on the game board
        game_board.get_unit(self.unit).position = self.to_hex
        game_board.update(self.unit)

    def undo(self, game_board):
        # Implement the logic to undo the move on the game board
        game_board.get_unit(self.unit).position = self.from_hex
        game_board.update(self.unit)

    def __repr__(self):
        return f"Move({self.unit}, {self.from_hex} -> {self.to_hex})"


class DeleteUnit(Action):
    def __init__(self, unit):
        self.unit = unit
        self.unit_visible = unit.visible
        self.unit_enabled = unit.enabled

    def do(self, game_board):
        # Implement the logic to delete the unit from the game board
        assert game_board.get_unit(self.unit.unit_id) is not None
        self.unit.visible = False

    def undo(self, game_board):
        assert game_board.get_unit(self.unit.unit_id) is not None
        self.unit.visible = self.unit_visible
        self.unit.enabled = self.unit_enabled

    def __repr__(self):
        return f"DeleteUnit({self.unit_id} at {self.position})"


class GameHistoryMixin:
    """Mixin class providing undo/redo history management for the Game class."""

    def _init_history(self):
        """Initialize history state. Call this in the Game __init__."""
        self._moves: list[Action] = []
        self._history_pointer = 0

    def enqueue(self, action: Action):
        """Add an action to the history and execute it."""
        if self._history_pointer < len(self._moves):
            self._moves = self._moves[: self._history_pointer]
            logging.getLogger("History").debug("Truncated move list due to new action")
        self._moves.append(action)
        action.do(self.board)
        self._history_pointer += 1
        logging.getLogger("History").debug(
            f"Added move: {action}, pointer at {self._history_pointer}"
        )

    def has_moves(self):
        """Check if there are any moves in the history."""
        return len(self._moves) > 0

    def undo(self):
        """Undo the last action."""
        if self._history_pointer > 0:
            self._history_pointer -= 1
            move = self._moves[self._history_pointer]
            move.undo(self.board)
            logging.getLogger("History").debug(
                f"Undid move: {move}, pointer at {self._history_pointer}"
            )
            return move
        logging.getLogger("History").debug("No move to undo")
        return None

    def redo(self):
        """Redo the next action."""
        if self._history_pointer < len(self._moves):
            move = self._moves[self._history_pointer]
            self._history_pointer += 1
            move.do(self.board)
            logging.getLogger("History").debug(
                f"Redid move: {move}, pointer at {self._history_pointer}"
            )
            return move

        logging.getLogger("History").debug("No move to redo")
        return None
