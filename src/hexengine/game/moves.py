from typing import Protocol

import logging
logger = logging.getLogger("UndoQueue")

class Action (Protocol):
    
    
    def do(self, game_board):
        ...

    def undo(self, game_board):
        ...
    


class Move (Action):
    def __init__(self, unit, from_hex, to_hex):
        self.unit = unit
        self.from_hex = from_hex
        self.to_hex = to_hex


    def do(self, game_board):
        # Implement the logic to move the unit on the game board
        game_board.get_unit(self.unit).position = self.to_hex    

    def undo(self, game_board):
        # Implement the logic to undo the move on the game board
        game_board.get_unit(self.unit).position = self.from_hex

    def __repr__(self):
        return f"Move({self.unit}, {self.from_hex} -> {self.to_hex})"


class DeleteUnit (Action):
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


class GameQueue:

    def __init__(self, gameboard=None):
        self._moves: list[Action] = []
        self.pointer  = 0
        self.gameboard = gameboard

    def enqueue(self, action: Action):
        if self.pointer < len(self._moves):
            self._moves = self._moves[:self.pointer]
            logger.debug("Truncated move list due to new action")
        self._moves.append(action)
        action.do(self.gameboard)
        self.pointer += 1    
        logger.debug(f"Added move: {action}, pointer at {self.pointer}")

    def has_moves(self):
        return len(self._moves) > 0
    
    def undo(self):
        if self.pointer > 0:
            self.pointer -= 1
            move = self._moves[self.pointer]
            move.undo(self.gameboard)
            logger.debug(f"Undid move: {move}, pointer at {self.pointer}")
            return move    
        return None
    
    def redo(self):
        if self.pointer < len(self._moves):
            move = self._moves[self.pointer]
            self.pointer += 1
            move.do(self.gameboard)
            return move
        return None