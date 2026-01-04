"""
Immutable game state models.

These represent the pure game state without any display or UI concerns.
All state models are frozen dataclasses for immutability and structural sharing.
"""

from dataclasses import dataclass, field, replace
from typing import Optional

from ..hexes.types import Hex


@dataclass(frozen=True)
class UnitState:
    """Pure state representation of a game unit.

    No display logic, no UI state - just the facts about this unit.
    """

    unit_id: str
    unit_type: str
    faction: str
    position: Hex
    health: int = 100
    active: bool = True

    def with_position(self, new_position: Hex) -> "UnitState":
        """Return a new UnitState with updated position."""
        return replace(self, position=new_position)

    def with_health(self, new_health: int) -> "UnitState":
        """Return a new UnitState with updated health."""
        return replace(self, health=new_health)

    def with_active(self, is_active: bool) -> "UnitState":
        """Return a new UnitState with updated active status."""
        return replace(self, active=is_active)


@dataclass(frozen=True)
class LocationState:
    """Pure state representation of a terrain location."""

    position: Hex
    terrain_type: str
    movement_cost: float

    def is_passable(self) -> bool:
        """Check if this location can be traversed."""
        return self.movement_cost != float("inf")


@dataclass(frozen=True)
class BoardState:
    """Immutable snapshot of the game board.

    Uses dictionaries for O(1) lookup. When state changes, only the
    affected dictionaries are copied - unchanged data is shared via references.
    """

    units: dict[str, UnitState] = field(default_factory=dict)
    locations: dict[Hex, LocationState] = field(default_factory=dict)

    def with_unit(self, unit: UnitState) -> "BoardState":
        """Return a new BoardState with the unit added or updated."""
        new_units = {**self.units, unit.unit_id: unit}
        return replace(self, units=new_units)

    def without_unit(self, unit_id: str) -> "BoardState":
        """Return a new BoardState with the unit removed."""
        new_units = {uid: u for uid, u in self.units.items() if uid != unit_id}
        return replace(self, units=new_units)

    def with_location(self, location: LocationState) -> "BoardState":
        """Return a new BoardState with the location added or updated."""
        new_locations = {**self.locations, location.position: location}
        return replace(self, locations=new_locations)

    def get_unit_at(self, position: Hex) -> Optional[UnitState]:
        """Find unit at the given position, if any."""
        for unit in self.units.values():
            if unit.position == position and unit.active:
                return unit
        return None

    def is_occupied(self, position: Hex) -> bool:
        """Check if a hex position is occupied by an active unit."""
        return self.get_unit_at(position) is not None

    def get_movement_cost(self, position: Hex) -> float:
        """Get the movement cost for a hex position."""
        location = self.locations.get(position)
        if location is None:
            return 1.0  # Default cost
        return location.movement_cost


@dataclass(frozen=True)
class TurnState:
    """State representing the current turn/phase/faction."""

    current_faction: str
    current_phase: str
    phase_actions_remaining: int
    turn_number: int = 1

    def with_actions_spent(self, amount: int = 1) -> "TurnState":
        """Return a new TurnState with actions spent."""
        return replace(
            self, phase_actions_remaining=self.phase_actions_remaining - amount
        )

    def with_next_phase(
        self, new_faction: str, new_phase: str, max_actions: int
    ) -> "TurnState":
        """Return a new TurnState for the next phase."""
        return replace(
            self,
            current_faction=new_faction,
            current_phase=new_phase,
            phase_actions_remaining=max_actions,
        )

    def with_next_turn(self, turn_number: int) -> "TurnState":
        """Return a new TurnState with incremented turn number."""
        return replace(self, turn_number=turn_number)


@dataclass(frozen=True)
class GameState:
    """
    Complete immutable game state.

    This is the single source of truth for the game. It's fully serializable
    and contains no display or UI concerns.
    """

    board: BoardState
    turn: TurnState

    def with_board(self, new_board: BoardState) -> "GameState":
        """Return a new GameState with updated board."""
        return replace(self, board=new_board)

    def with_turn(self, new_turn: TurnState) -> "GameState":
        """Return a new GameState with updated turn."""
        return replace(self, turn=new_turn)

    @classmethod
    def create_empty(
        cls, initial_faction: str = "Blue", initial_phase: str = "Movement"
    ) -> "GameState":
        """Create a new empty game state."""
        return cls(
            board=BoardState(),
            turn=TurnState(
                current_faction=initial_faction,
                current_phase=initial_phase,
                phase_actions_remaining=2,
                turn_number=1,
            ),
        )
