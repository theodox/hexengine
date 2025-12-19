from typing import Protocol


class Action(Protocol):
    def do(self, game_board): ...

    def undo(self, game_board): ...
