"""
Action manager - the gatekeeper for all game state mutations.

This is the ONLY way to permanently modify game state. It provides:
- Centralized state management
- Undo/redo functionality
- State change notifications
- Event sourcing (action history)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable

from .game_state import GameState


class StateAction(ABC):
    """Abstract base class for actions that modify game state.

    Remember these are pure functions, they return new
    Gamestate instances without mutating the original.
    """

    @abstractmethod
    def apply(self, state: GameState) -> GameState:
        """Apply this action to a state, returning a new state."""
        ...

    @abstractmethod
    def revert(self, state: GameState) -> GameState:
        """Reverse this action on a state, returning a new state."""
        ...

    @abstractmethod
    def should_revert_prior(self) -> bool:
        """Indicate if prior actions should be reverted when undoing this action."""
        ...


class ActionManager:
    """Manages game state transitions through actions.

    All permanent state changes must go through this manager's execute() method.
    """

    def __init__(self, initial_state: GameState):
        self._current_state = initial_state
        self._history: list[StateAction] = []
        self._pointer = 0
        self._observers: list[Callable[[GameState], None]] = []
        self.logger = logging.getLogger("action_manager")

    @property
    def current_state(self) -> GameState:
        """Read-only access to the current committed game state."""
        return self._current_state

    def execute(self, action: StateAction) -> GameState:
        """Execute an action, permanently modifying game state.

        This is the ONLY way to change committed game state.

        Args:
            action: The action to execute

        Returns:
            The new game state after applying the action
        """
        # Truncate history if we're not at the end (branching timeline)
        if self._pointer < len(self._history):
            self._history = self._history[: self._pointer]
            self.logger.debug(f"Truncated history at pointer {self._pointer}")

        # Apply action to get new state
        try:
            new_state = action.apply(self._current_state)
        except Exception as e:
            self.logger.error(f"Failed to apply action {action}: {e}")
            raise

        # Commit the change
        self._history.append(action)
        self._current_state = new_state
        self._pointer += 1

        self.logger.info(f"Executed action {action} (#{self._pointer})")

        # Notify observers
        self._notify_observers(new_state)

        return new_state

    def undo(self) -> GameState | None:
        """Undo the last action.

        Returns:
            The new state after undoing, or None if nothing to undo
        """
        if self._pointer == 0:
            self.logger.debug("Nothing to undo")
            return None

        self._pointer -= 1
        action = self._history[self._pointer]

        try:
            new_state = action.revert(self._current_state)
            self._current_state = new_state

            if action.should_revert_prior() and self._pointer > 0:
                new_state = self._history[self._pointer - 1].revert(new_state)
                self._pointer -= 1
                # Also revert prior action if applicable
        except Exception as e:
            self.logger.error(f"Failed to revert action {action}: {e}")
            self._pointer += 1  # Restore pointer
            raise

        self._current_state = new_state
        self.logger.info(f"Undid action {action} (now at #{self._pointer})")

        # Notify observers
        self._notify_observers(new_state)

        return new_state

    def redo(self) -> GameState | None:
        """Redo the next action in history.

        Returns:
            The new state after redoing, or None if nothing to redo
        """
        if self._pointer >= len(self._history):
            self.logger.debug("Nothing to redo")
            return None

        action = self._history[self._pointer]

        try:
            new_state = action.apply(self._current_state)
        except Exception as e:
            self.logger.error(f"Failed to reapply action {action}: {e}")
            raise

        self._current_state = new_state
        self._pointer += 1
        self.logger.info(f"Redid action {action} (#{self._pointer})")

        # Notify observers
        self._notify_observers(new_state)

        return new_state

    def replace_state(self, new_state: GameState) -> None:
        """Replace committed state and clear undo/redo history."""
        self._current_state = new_state
        self._history = []
        self._pointer = 0
        self._notify_observers(new_state)

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return self._pointer > 0

    def can_redo(self) -> bool:
        """Check if redo is available."""
        return self._pointer < len(self._history)

    def add_observer(self, observer: Callable[[GameState], None]) -> None:
        """Add an observer to be notified of state changes.

        Observers are called after each state change (execute/undo/redo).
        Use this to sync display with state.
        """
        self._observers.append(observer)

    def __iadd__(self, observer: Callable[[GameState], None]) -> ActionManager:
        """Shortcut to add an observer using += syntax."""
        self.add_observer(observer)
        return self

    def remove_observer(self, observer: Callable[[GameState], None]) -> None:
        """Remove an observer."""
        if observer in self._observers:
            self._observers.remove(observer)

    def __isub__(self, observer: Callable[[GameState], None]) -> ActionManager:
        """Shortcut to remove an observer using -= syntax."""
        self.remove_observer(observer)
        return self

    def _notify_observers(self, new_state: GameState) -> None:
        """Notify all observers of a state change."""
        for observer in self._observers:
            try:
                observer(new_state)
            except Exception as e:
                self.logger.error(f"Observer {observer} failed: {e}")

    def get_history_size(self) -> int:
        """Get the number of actions in history."""
        return len(self._history)

    def __len__(self) -> int:
        """Get the number of actions in history."""
        return len(self._history)

    def get_pointer_position(self) -> int:
        """Get the current position in history."""
        return self._pointer
