from .base import Action


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
        return f"<DELETE '{self.unit_id}'>"
