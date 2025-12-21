from hexengine.actions import Action
from .events.hotkey import Hotkey, Modifiers

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
            self.logger.debug("Truncated move list due to new action")
        self._moves.append(action)
        action.do(self.board)
        self._history_pointer += 1
        self.logger.info(
            f"ENQUEUE {action} #{self._history_pointer}"
        )

    def has_moves(self):
        """Check if there are any moves in the history."""
        return len(self._moves) > 0

    @Hotkey('z', Modifiers.CONTROL)
    def undo(self):
        """Undo the last action."""
        if self._history_pointer > 0:
            self._history_pointer -= 1
            move = self._moves[self._history_pointer]
            move.undo(self.board)
            self.logger.info(
                f"UNDO {move} #{self._history_pointer}"
            )
            return move
        self.logger.debug("No move to undo")
        return None

    @Hotkey('y', Modifiers.CONTROL)
    def redo(self):
        """Redo the next action."""
        if self._history_pointer < len(self._moves):
            move = self._moves[self._history_pointer]
            self._history_pointer += 1
            move.do(self.board)
            self.logger.info(
                f"REDO {move} #{self._history_pointer}"
            )
            return move

        self.logger.debug("No move to redo")
        return None
