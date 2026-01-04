"""
State-based actions for the immutable state system.
"""

from typing import TYPE_CHECKING

from .action_manager import StateAction

if TYPE_CHECKING:
    from ..hexes.types import Hex
    from ..state.game_state import GameState


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

        # Restore previous action count
        new_turn = replace(state.turn, phase_actions_remaining=self.previous_remaining)

        # Create new game state with updated turn
        return state.with_turn(new_turn)

    def __repr__(self) -> str:
        return f"<SpendAction {self.amount}>"
