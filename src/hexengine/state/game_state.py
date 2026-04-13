"""
Immutable game state models.

These represent the pure game state without any display or UI concerns.
All state models are frozen dataclasses for immutability and structural sharing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

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

    def with_position(self, new_position: Hex) -> UnitState:
        """Return a new UnitState with updated position."""
        return replace(self, position=new_position)

    def with_health(self, new_health: int) -> UnitState:
        """Return a new UnitState with updated health."""
        return replace(self, health=new_health)

    def with_active(self, is_active: bool) -> UnitState:
        """Return a new UnitState with updated active status."""
        return replace(self, active=is_active)


@dataclass(frozen=True)
class LocationState:
    """Pure state representation of a terrain location."""

    position: Hex
    terrain_type: str
    movement_cost: float
    hex_color: str | None = None
    assault_modifier: float = 0.0
    ranged_modifier: float = 0.0
    block_los: bool = True

    def is_passable(self) -> bool:
        """Check if this location can be traversed."""
        return self.movement_cost != float("inf")


@dataclass(frozen=True)
class UnsetTerrainDefaults:
    """Terrain applied to any hex not listed in `BoardState.locations`."""

    terrain_type: str
    movement_cost: float
    hex_color: str | None = None
    assault_modifier: float = 0.0
    ranged_modifier: float = 0.0
    block_los: bool = True


@dataclass(frozen=True)
class BoardState:
    """Immutable snapshot of the game board.

    Uses dictionaries for O(1) lookup. When state changes, only the
    affected dictionaries are copied - unchanged data is shared via references.
    """

    units: dict[str, UnitState] = field(default_factory=dict)
    locations: dict[Hex, LocationState] = field(default_factory=dict)
    #: From scenario `[[terrain_types]]` row with `default = true`; `None` = legacy 1.0 cost.
    unset_defaults: UnsetTerrainDefaults | None = None

    def with_unit(self, unit: UnitState) -> BoardState:
        """Return a new BoardState with the unit added or updated."""
        new_units = {**self.units, unit.unit_id: unit}
        return replace(self, units=new_units)

    def without_unit(self, unit_id: str) -> BoardState:
        """Return a new BoardState with the unit removed."""
        new_units = {uid: u for uid, u in self.units.items() if uid != unit_id}
        return replace(self, units=new_units)

    def with_location(self, location: LocationState) -> BoardState:
        """Return a new BoardState with the location added or updated."""
        new_locations = {**self.locations, location.position: location}
        return replace(self, locations=new_locations)

    def get_unit_at(self, position: Hex) -> UnitState | None:
        """Find unit at the given position, if any."""
        for unit in self.units.values():
            if unit.position == position and unit.active:
                return unit
        return None

    def is_occupied(self, position: Hex) -> bool:
        """Check if a hex position is occupied by an active unit."""
        return self.get_unit_at(position) is not None

    def explicit_location(self, position: Hex) -> LocationState | None:
        """Terrain from the scenario `[[terrain_groups]]` only (no unset fill)."""
        return self.locations.get(position)

    def effective_location(self, position: Hex) -> LocationState | None:
        """Terrain for movement and rules: explicit hex, else scenario unset-default template."""
        loc = self.locations.get(position)
        if loc is not None:
            return loc
        if self.unset_defaults is None:
            return None
        d = self.unset_defaults
        return LocationState(
            position=position,
            terrain_type=d.terrain_type,
            movement_cost=d.movement_cost,
            hex_color=d.hex_color,
            assault_modifier=d.assault_modifier,
            ranged_modifier=d.ranged_modifier,
            block_los=d.block_los,
        )

    def get_movement_cost(self, position: Hex) -> float:
        """Movement cost for a hex (explicit terrain, else `unset_defaults`, else 1.0)."""
        loc = self.effective_location(position)
        if loc is None:
            return 1.0
        return loc.movement_cost


@dataclass(frozen=True)
class TurnState:
    """State representing the current turn/phase/faction."""

    current_faction: str
    current_phase: str
    phase_actions_remaining: int
    turn_number: int = 1
    #: Index into the match turn rota (`GameDefinition.turn_order()`); authoritative for sequencing.
    schedule_index: int = 0

    def with_actions_spent(self, amount: int = 1) -> TurnState:
        """Return a new TurnState with actions spent."""
        return replace(
            self, phase_actions_remaining=self.phase_actions_remaining - amount
        )

    def with_next_phase(
        self,
        new_faction: str,
        new_phase: str,
        max_actions: int,
        *,
        schedule_index: int,
    ) -> TurnState:
        """Return a new TurnState for the next phase."""
        return replace(
            self,
            current_faction=new_faction,
            current_phase=new_phase,
            phase_actions_remaining=max_actions,
            schedule_index=schedule_index,
        )

    def with_next_turn(self, turn_number: int) -> TurnState:
        """Return a new TurnState with incremented turn number."""
        return replace(self, turn_number=turn_number)


@dataclass(frozen=True)
class GameState:
    """
    Complete immutable game state.

    This is the single source of truth for the game. It's fully serializable
    and contains no display or UI concerns.

    `extension` holds optional JSON-safe game-specific data (namespaced by game id).
    `rng_log` is an append-only record of server-authoritative random draws (replay/debug).
    """

    board: BoardState
    turn: TurnState
    extension: dict[str, Any] = field(default_factory=dict)
    rng_log: tuple[dict[str, Any], ...] = ()

    def with_board(self, new_board: BoardState) -> GameState:
        """Return a new GameState with updated board."""
        return replace(self, board=new_board)

    def with_turn(self, new_turn: TurnState) -> GameState:
        """Return a new GameState with updated turn."""
        return replace(self, turn=new_turn)

    def with_extension(self, extension: dict[str, Any]) -> GameState:
        """Replace extension payload (shallow copy of dict)."""
        return replace(self, extension=dict(extension))

    def with_rng_log(self, rng_log: tuple[dict[str, Any], ...]) -> GameState:
        """Replace RNG log (immutable tuple)."""
        return replace(self, rng_log=rng_log)

    @classmethod
    def create_empty(
        cls,
        initial_faction: str = "Red",
        initial_phase: str = "Movement",
        *,
        phase_actions_remaining: int = 2,
        schedule_index: int = 0,
    ) -> GameState:
        """Create a new empty game state."""
        return cls(
            board=BoardState(),
            turn=TurnState(
                current_faction=initial_faction,
                current_phase=initial_phase,
                phase_actions_remaining=phase_actions_remaining,
                turn_number=1,
                schedule_index=schedule_index,
            ),
        )
