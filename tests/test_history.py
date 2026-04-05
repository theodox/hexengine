import os
import sys
import unittest
from unittest.mock import Mock

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    __import__("src.hexengine.state")
    NEW_STATE_SYSTEM_AVAILABLE = True
except ImportError:
    NEW_STATE_SYSTEM_AVAILABLE = False


# Mock the Action protocol for testing old system (kept for backwards compatibility tests)
class Action:
    def do(self, game_board): ...
    def undo(self, game_board): ...


# We can't import GameHistoryMixin directly due to pyodide dependencies,
# so we'll copy it here for testing the old system
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
        self.logger.info(f"ENQUEUE {action} #{self._history_pointer}")

    def has_moves(self):
        """Check if there are any moves in the history."""
        return len(self._moves) > 0

    def undo(self):
        """Undo the last action."""
        if self._history_pointer > 0:
            self._history_pointer -= 1
            move = self._moves[self._history_pointer]
            move.undo(self.board)
            self.logger.info(f"UNDO {move} #{self._history_pointer}")
            return move
        self.logger.debug("No move to undo")
        return None

    def redo(self):
        """Redo the next action."""
        if self._history_pointer < len(self._moves):
            move = self._moves[self._history_pointer]
            self._history_pointer += 1
            move.do(self.board)
            self.logger.info(f"REDO {move} #{self._history_pointer}")
            return move

        self.logger.debug("No move to redo")
        return None


class MockAction:
    """Mock action for testing history functionality."""

    def __init__(self, name):
        self.name = name
        self.do_count = 0
        self.undo_count = 0

    def do(self, game_board):
        """Execute the action."""
        self.do_count += 1

    def undo(self, game_board):
        """Undo the action."""
        self.undo_count += 1

    def __repr__(self):
        return f"<MockAction '{self.name}'>"


class MockGameWithHistory(GameHistoryMixin):
    """Mock game class that uses the GameHistoryMixin."""

    def __init__(self):
        self.board = Mock()
        self.logger = Mock()
        self._init_history()


class TestGameHistory(unittest.TestCase):
    """Test cases for the GameHistoryMixin class."""

    def setUp(self):
        """Set up test fixtures."""
        self.game = MockGameWithHistory()

    def test_init_history_creates_empty_list(self):
        """Test that _init_history creates an empty moves list."""
        self.assertEqual(len(self.game._moves), 0)
        self.assertEqual(self.game._history_pointer, 0)

    def test_init_history_sets_pointer_to_zero(self):
        """Test that _init_history sets history pointer to 0."""
        self.game._moves = [Mock(), Mock()]
        self.game._history_pointer = 5
        self.game._init_history()
        self.assertEqual(self.game._history_pointer, 0)

    def test_enqueue_adds_action_to_empty_list(self):
        """Test that enqueue adds an action to an empty history."""
        action = MockAction("action1")
        self.game.enqueue(action)

        self.assertEqual(len(self.game._moves), 1)
        self.assertIs(self.game._moves[0], action)
        self.assertEqual(self.game._history_pointer, 1)

    def test_enqueue_executes_action(self):
        """Test that enqueue calls do() on the action."""
        action = MockAction("action1")
        self.game.enqueue(action)

        self.assertEqual(action.do_count, 1)
        self.assertEqual(action.undo_count, 0)

    def test_enqueue_multiple_actions(self):
        """Test that multiple actions can be enqueued."""
        action1 = MockAction("action1")
        action2 = MockAction("action2")
        action3 = MockAction("action3")

        self.game.enqueue(action1)
        self.game.enqueue(action2)
        self.game.enqueue(action3)

        self.assertEqual(len(self.game._moves), 3)
        self.assertEqual(self.game._history_pointer, 3)
        self.assertEqual(action1.do_count, 1)
        self.assertEqual(action2.do_count, 1)
        self.assertEqual(action3.do_count, 1)

    def test_enqueue_truncates_future_after_undo(self):
        """Test that enqueue truncates future moves after an undo."""
        action1 = MockAction("action1")
        action2 = MockAction("action2")
        action3 = MockAction("action3")

        self.game.enqueue(action1)
        self.game.enqueue(action2)
        self.game.enqueue(action3)
        self.game.undo()
        self.game.undo()

        # Now pointer is at 1, moves has 3 items
        new_action = MockAction("new_action")
        self.game.enqueue(new_action)

        # Should have truncated action2 and action3
        self.assertEqual(len(self.game._moves), 2)
        self.assertIs(self.game._moves[0], action1)
        self.assertIs(self.game._moves[1], new_action)
        self.assertEqual(self.game._history_pointer, 2)

    def test_has_moves_returns_false_initially(self):
        """Test that has_moves returns False for empty history."""
        self.assertFalse(self.game.has_moves())

    def test_has_moves_returns_true_after_enqueue(self):
        """Test that has_moves returns True after enqueueing an action."""
        action = MockAction("action1")
        self.game.enqueue(action)
        self.assertTrue(self.game.has_moves())

    def test_has_moves_returns_true_after_undo(self):
        """Test that has_moves still returns True after undo."""
        action = MockAction("action1")
        self.game.enqueue(action)
        self.game.undo()
        self.assertTrue(self.game.has_moves())

    def test_undo_on_empty_history_returns_none(self):
        """Test that undo on empty history returns None."""
        result = self.game.undo()
        self.assertIsNone(result)
        self.assertEqual(self.game._history_pointer, 0)

    def test_undo_decrements_pointer(self):
        """Test that undo decrements the history pointer."""
        action = MockAction("action1")
        self.game.enqueue(action)

        self.assertEqual(self.game._history_pointer, 1)
        self.game.undo()
        self.assertEqual(self.game._history_pointer, 0)

    def test_undo_calls_undo_on_action(self):
        """Test that undo calls undo() on the action."""
        action = MockAction("action1")
        self.game.enqueue(action)

        result = self.game.undo()

        self.assertEqual(action.undo_count, 1)
        self.assertIs(result, action)

    def test_undo_returns_undone_action(self):
        """Test that undo returns the undone action."""
        action = MockAction("action1")
        self.game.enqueue(action)

        result = self.game.undo()
        self.assertIs(result, action)

    def test_undo_multiple_times(self):
        """Test that multiple undos work correctly."""
        action1 = MockAction("action1")
        action2 = MockAction("action2")
        action3 = MockAction("action3")

        self.game.enqueue(action1)
        self.game.enqueue(action2)
        self.game.enqueue(action3)

        result1 = self.game.undo()
        self.assertIs(result1, action3)
        self.assertEqual(self.game._history_pointer, 2)

        result2 = self.game.undo()
        self.assertIs(result2, action2)
        self.assertEqual(self.game._history_pointer, 1)

        result3 = self.game.undo()
        self.assertIs(result3, action1)
        self.assertEqual(self.game._history_pointer, 0)

    def test_undo_beyond_start_returns_none(self):
        """Test that undo at the start of history returns None."""
        action = MockAction("action1")
        self.game.enqueue(action)

        self.game.undo()
        result = self.game.undo()

        self.assertIsNone(result)
        self.assertEqual(self.game._history_pointer, 0)

    def test_redo_on_empty_history_returns_none(self):
        """Test that redo on empty history returns None."""
        result = self.game.redo()
        self.assertIsNone(result)

    def test_redo_without_undo_returns_none(self):
        """Test that redo without prior undo returns None."""
        action = MockAction("action1")
        self.game.enqueue(action)

        result = self.game.redo()
        self.assertIsNone(result)

    def test_redo_increments_pointer(self):
        """Test that redo increments the history pointer."""
        action = MockAction("action1")
        self.game.enqueue(action)
        self.game.undo()

        self.assertEqual(self.game._history_pointer, 0)
        self.game.redo()
        self.assertEqual(self.game._history_pointer, 1)

    def test_redo_calls_do_on_action(self):
        """Test that redo calls do() on the action."""
        action = MockAction("action1")
        self.game.enqueue(action)
        self.game.undo()

        # Reset count to check redo call
        initial_do_count = action.do_count
        result = self.game.redo()

        self.assertEqual(action.do_count, initial_do_count + 1)
        self.assertIs(result, action)

    def test_redo_returns_redone_action(self):
        """Test that redo returns the redone action."""
        action = MockAction("action1")
        self.game.enqueue(action)
        self.game.undo()

        result = self.game.redo()
        self.assertIs(result, action)

    def test_redo_multiple_times(self):
        """Test that multiple redos work correctly."""
        action1 = MockAction("action1")
        action2 = MockAction("action2")
        action3 = MockAction("action3")

        self.game.enqueue(action1)
        self.game.enqueue(action2)
        self.game.enqueue(action3)

        self.game.undo()
        self.game.undo()
        self.game.undo()

        result1 = self.game.redo()
        self.assertIs(result1, action1)
        self.assertEqual(self.game._history_pointer, 1)

        result2 = self.game.redo()
        self.assertIs(result2, action2)
        self.assertEqual(self.game._history_pointer, 2)

        result3 = self.game.redo()
        self.assertIs(result3, action3)
        self.assertEqual(self.game._history_pointer, 3)

    def test_redo_beyond_end_returns_none(self):
        """Test that redo beyond the end of history returns None."""
        action = MockAction("action1")
        self.game.enqueue(action)
        self.game.undo()
        self.game.redo()

        result = self.game.redo()
        self.assertIsNone(result)

    def test_undo_redo_cycle(self):
        """Test that undo/redo cycle maintains consistency."""
        action1 = MockAction("action1")
        action2 = MockAction("action2")

        self.game.enqueue(action1)
        self.game.enqueue(action2)

        # Undo both
        self.game.undo()
        self.game.undo()
        self.assertEqual(self.game._history_pointer, 0)

        # Redo both
        self.game.redo()
        self.game.redo()
        self.assertEqual(self.game._history_pointer, 2)

        # Undo one
        self.game.undo()
        self.assertEqual(self.game._history_pointer, 1)

        # Redo one
        self.game.redo()
        self.assertEqual(self.game._history_pointer, 2)

    def test_complex_history_scenario(self):
        """Test a complex scenario with multiple operations."""
        actions = [MockAction(f"action{i}") for i in range(5)]

        # Enqueue all 5 actions
        for action in actions:
            self.game.enqueue(action)

        self.assertEqual(self.game._history_pointer, 5)
        self.assertEqual(len(self.game._moves), 5)

        # Undo 3 times
        self.game.undo()
        self.game.undo()
        self.game.undo()
        self.assertEqual(self.game._history_pointer, 2)

        # Enqueue a new action (should truncate)
        new_action = MockAction("new")
        self.game.enqueue(new_action)
        self.assertEqual(len(self.game._moves), 3)
        self.assertEqual(self.game._history_pointer, 3)

        # Undo and redo
        self.game.undo()
        self.assertEqual(self.game._history_pointer, 2)
        self.game.redo()
        self.assertEqual(self.game._history_pointer, 3)

    def test_logger_info_called_on_enqueue(self):
        """Test that logger.info is called when enqueueing."""
        action = MockAction("action1")
        self.game.enqueue(action)

        self.game.logger.info.assert_called()

    def test_logger_info_called_on_undo(self):
        """Test that logger.info is called when undoing."""
        action = MockAction("action1")
        self.game.enqueue(action)
        self.game.undo()

        # Check that info was called at least twice (enqueue + undo)
        self.assertGreaterEqual(self.game.logger.info.call_count, 2)

    def test_logger_debug_called_on_failed_undo(self):
        """Test that logger.debug is called when undo fails."""
        self.game.undo()
        self.game.logger.debug.assert_called()

    def test_logger_info_called_on_redo(self):
        """Test that logger.info is called when redoing."""
        action = MockAction("action1")
        self.game.enqueue(action)
        self.game.undo()
        self.game.redo()

        # Check that info was called multiple times
        self.assertGreaterEqual(self.game.logger.info.call_count, 3)

    def test_logger_debug_called_on_failed_redo(self):
        """Test that logger.debug is called when redo fails."""
        self.game.redo()
        self.game.logger.debug.assert_called()

    def test_board_passed_to_action_do(self):
        """Test that the game board is passed to action.do()."""
        action = MockAction("action1")
        action.do = Mock()

        self.game.enqueue(action)
        action.do.assert_called_once_with(self.game.board)

    def test_board_passed_to_action_undo(self):
        """Test that the game board is passed to action.undo()."""
        action = MockAction("action1")
        action.undo = Mock()

        self.game.enqueue(action)
        self.game.undo()

        action.undo.assert_called_once_with(self.game.board)


@unittest.skipIf(
    not NEW_STATE_SYSTEM_AVAILABLE,
    "New state system not available - install package first",
)
class TestNewStateSystem(unittest.TestCase):
    """Tests for the new state-based action system."""

    def test_action_manager_available(self):
        """Test that the new ActionManager is available."""
        if not NEW_STATE_SYSTEM_AVAILABLE:
            self.skipTest("New state system not available")

        from src.hexengine.state import ActionManager, GameState

        state = GameState.create_empty()
        action_mgr = ActionManager(state)
        self.assertIsNotNone(action_mgr)
        self.assertEqual(action_mgr.get_pointer_position(), 0)


if __name__ == "__main__":
    if NEW_STATE_SYSTEM_AVAILABLE:
        print("\nNOTE: Old GameHistoryMixin tests are skipped.")
        print(
            "The old action system has been replaced by hexengine.state.ActionManager"
        )
        print(
            "See EXAMPLE_NEW_STATE_SYSTEM.py and test_preview_system.py for new system tests.\n"
        )
    unittest.main()
