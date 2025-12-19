from .base import Action


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
        return f"<MOVE '{self.unit}', {self.from_hex} -> {self.to_hex}>"
