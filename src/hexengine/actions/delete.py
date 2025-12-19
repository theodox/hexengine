from .base import Action


class DeleteUnit(Action):
    def __init__(self, unit):
        self.unit = unit
        self.unit_enabled = unit.enabled

    def do(self, game_board):
        # Implement the logic to delete the unit from the game board
        assert game_board.get_unit(self.unit.unit_id) is not None
        self.unit.visible = False
        game_board.update(self.unit)

    def undo(self, game_board):
        assert game_board.get_unit(self.unit.unit_id) is not None
        self.unit.active = True
        game_board.update(self.unit)

    def __repr__(self):
        return f"<DELETE '{self.unit.unit_id}'>"
