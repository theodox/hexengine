from typing import Optional

from ..actions import Action
from .events.hotkey import Hotkey, Modifiers

# Flag to enable new state system (set to True to use new system)
USE_NEW_STATE_SYSTEM = True


class GameHistoryMixin:
    """Mixin class providing undo/redo history management for the Game class."""

    def _init_history(self) -> None:
        """Initialize history state. Call this in the Game __init__."""
        self._moves: list[Action] = []
        self._history_pointer = 0

    def enqueue(self, action: Action) -> None:
        """Add an action to the history and execute it."""
        if self._history_pointer < len(self._moves):
            self._moves = self._moves[: self._history_pointer]
            self.logger.debug("Truncated move list due to new action")
        self._moves.append(action)
        action.do(self.board)
        self._history_pointer += 1
        faction, phase = self.turn_manager.current
        self.turn_manager.spend_action()
        self.logger.info(f"ENQUEUE {action} #{self._history_pointer}")

    def has_moves(self) -> bool:
        """Check if there are any moves in the history."""
        return len(self._moves) > 0

    @Hotkey("z", Modifiers.CONTROL)
    def undo(self) -> Optional[Action]:
        """Undo the last action."""
        if USE_NEW_STATE_SYSTEM:
            # New system: use ActionManager
            if hasattr(self, 'action_mgr') and self.action_mgr.can_undo():
                self.action_mgr.undo()
                self.logger.info("UNDO (new system)")
                return None  # New system doesn't return action
            self.logger.debug("No move to undo (new system)")
            return None
        else:
            # Old system
            if self._history_pointer > 0:
                self._history_pointer -= 1
                move = self._moves[self._history_pointer]
                move.undo(self.board)
                self.logger.info(f"UNDO {move} #{self._history_pointer}")
                return move
            self.logger.debug("No move to undo")
            return None

    @Hotkey("y", Modifiers.CONTROL)
    def redo(self) -> Optional[Action]:
        """Redo the next action."""
        if USE_NEW_STATE_SYSTEM:
            # New system: use ActionManager
            if hasattr(self, 'action_mgr') and self.action_mgr.can_redo():
                self.action_mgr.redo()
                self.logger.info("REDO (new system)")
                return None  # New system doesn't return action
            self.logger.debug("No move to redo (new system)")
            return None
        else:
            # Old system
            if self._history_pointer < len(self._moves):
                move = self._moves[self._history_pointer]
                self._history_pointer += 1
                move.do(self.board)
                self.logger.info(f"REDO {move} #{self._history_pointer}")
                return move

            self.logger.debug("No move to redo")
            return None
