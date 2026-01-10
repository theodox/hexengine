"""
State-based actions for the immutable state system.
"""
import logging
from typing import TYPE_CHECKING

from .action_manager import StateAction

if TYPE_CHECKING:
    from ..hexes.types import Hex
    from ..state.game_state import GameState

LOGGER = logging.getLogger("actions")

class MoveUnit(StateAction):
    """Action to move a unit from one hex to another.

    This is a pure state transformation - no side effects, no mutations.
    """

    def __init__(self, unit_id: str, from_hex: "Hex", to_hex: "Hex"):
        self.unit_id = unit_id
        self.from_hex = from_hex
        self.to_hex = to_hex

    def apply(self, state: "GameState") -> "GameState":
        """Apply the move, returning a new game state."""
        # Get the unit
        unit = state.board.units.get(self.unit_id)
        if unit is None:
            raise ValueError(f"Unit {self.unit_id} not found in state")

        # Verify it's at the expected position
        if unit.position != self.from_hex:
            raise ValueError(
                f"Unit {self.unit_id} is at {unit.position}, not at expected {self.from_hex}"
            )

        # Create new unit with new position
        new_unit = unit.with_position(self.to_hex)

        # Create new board with updated unit
        new_board = state.board.with_unit(new_unit)

        # Create new game state with updated board
        return state.with_board(new_board)

    def revert(self, state: "GameState") -> "GameState":
        """Revert the move, returning a new game state."""
        # Get the unit
        unit = state.board.units.get(self.unit_id)
        if unit is None:
            raise ValueError(f"Unit {self.unit_id} not found in state")

        # Create new unit with original position
        new_unit = unit.with_position(self.from_hex)

        # Create new board with updated unit
        new_board = state.board.with_unit(new_unit)

        # Create new game state with updated board
        return state.with_board(new_board)
    
    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"<MoveUnit '{self.unit_id}', {self.from_hex} -> {self.to_hex}>"


class DeleteUnit(StateAction):
    """Action to deactivate a unit (soft delete).

    Sets the unit's active flag to False rather than removing it entirely.
    This allows for undo and preserves the unit's data.
    """

    def __init__(self, unit_id: str):
        self.unit_id = unit_id

    def apply(self, state: "GameState") -> "GameState":
        """Deactivate the unit, returning a new game state."""
        # Get the unit
        unit = state.board.units.get(self.unit_id)
        if unit is None:
            raise ValueError(f"Unit {self.unit_id} not found in state")

        # Create new unit with active=False
        new_unit = unit.with_active(False)

        # Create new board with updated unit
        new_board = state.board.with_unit(new_unit)

        # Create new game state with updated board
        return state.with_board(new_board)

    def revert(self, state: "GameState") -> "GameState":
        """Reactivate the unit, returning a new game state."""
        # Get the unit
        unit = state.board.units.get(self.unit_id)
        if unit is None:
            raise ValueError(f"Unit {self.unit_id} not found in state")

        # Create new unit with active=True
        new_unit = unit.with_active(True)

        # Create new board with updated unit
        new_board = state.board.with_unit(new_unit)

        # Create new game state with updated board
        return state.with_board(new_board)
    
    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"<DeleteUnit '{self.unit_id}'>"


class AddUnit(StateAction):
    """Action to add a new unit to the game."""

    def __init__(
        self,
        unit_id: str,
        unit_type: str,
        faction: str,
        position: "Hex",
        health: int = 100,
    ):
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.faction = faction
        self.position = position
        self.health = health

    def apply(self, state: "GameState") -> "GameState":
        """Add the unit, returning a new game state."""
        from ..state.game_state import UnitState

        # Check if unit already exists
        if self.unit_id in state.board.units:
            raise ValueError(f"Unit {self.unit_id} already exists")

        # Check if position is occupied
        if state.board.is_occupied(self.position):
            raise ValueError(f"Position {self.position} is already occupied")

        # Create new unit
        new_unit = UnitState(
            unit_id=self.unit_id,
            unit_type=self.unit_type,
            faction=self.faction,
            position=self.position,
            health=self.health,
            active=True,
        )

        # Create new board with added unit
        new_board = state.board.with_unit(new_unit)

        # Create new game state with updated board
        return state.with_board(new_board)

    def revert(self, state: "GameState") -> "GameState":
        """Remove the unit, returning a new game state."""
        # Create new board without the unit
        new_board = state.board.without_unit(self.unit_id)

        # Create new game state with updated board
        return state.with_board(new_board)
    
    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"<AddUnit '{self.unit_id}' ({self.faction} {self.unit_type}) at {self.position}>"


class SpendAction(StateAction):
    """Action to spend action points in the current phase."""

    def __init__(self, amount: int = 1):
        self.amount = amount
        self.previous_remaining = None  # Stored for undo

    def apply(self, state: "GameState") -> "GameState":
        """Spend actions, returning a new game state."""
        # Store previous value for undo
        self.previous_remaining = state.turn.phase_actions_remaining

        # Create new turn state with actions spent
        new_turn = state.turn.with_actions_spent(self.amount)

        # Create new game state with updated turn
        return state.with_turn(new_turn)

    def revert(self, state: "GameState") -> "GameState":
        """Restore spent actions, returning a new game state."""
        from dataclasses import replace

        current_phase = state.turn.current_phase
        current_faction = state.turn.current_faction

        # Restore previous action count
        new_turn = replace(state.turn, phase_actions_remaining=self.previous_remaining)
        
        if new_turn.current_phase != current_phase or new_turn.current_faction != current_faction:
            LOGGER.warning("Phase or faction changed since SpendAction was applied; cannot revert accurately.")
            return state  # No change if phase/faction differ

        # Create new game state with updated turn
        return state.with_turn(new_turn)

    def should_revert_prior(self):
        return True

    def __repr__(self) -> str:
        return f"<SpendAction {self.amount}>"

class NextPhase(StateAction):
    """Action to advance to the next phase/turn."""

    def __init__(self, new_faction: str, new_phase: str, max_actions: int):
        self.new_faction = new_faction
        self.new_phase = new_phase
        self.max_actions = max_actions
        # Store previous values for undo
        self.prev_faction = None
        self.prev_phase = None
        self.prev_actions = None

    def apply(self, state: "GameState") -> "GameState":
        """Advance to next phase, returning a new game state."""
        # Store previous values for undo
        self.prev_faction = state.turn.current_faction
        self.prev_phase = state.turn.current_phase
        self.prev_actions = state.turn.phase_actions_remaining

        # Create new turn state for next phase
        new_turn = state.turn.with_next_phase(
            self.new_faction, self.new_phase, self.max_actions
        )

        # Create new game state with updated turn
        return state.with_turn(new_turn)

    def revert(self, state: "GameState") -> "GameState":
        """Restore previous phase, returning a new game state."""
        # Restore previous phase
        new_turn = state.turn.with_next_phase(
            self.prev_faction, self.prev_phase, self.prev_actions
        )

        # Create new game state with updated turn
        return state.with_turn(new_turn)

    def should_revert_prior(self):
        return False
    
    def __repr__(self) -> str:
        return f"<NextPhase {self.new_faction}-{self.new_phase}>"
