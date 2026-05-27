"""
Immutable game state models.

These represent the pure game state without any display or UI concerns.
All state models are frozen dataclasses for immutability and structural sharing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from ..hexes.edges import EdgeKey
from ..hexes.types import Hex


@dataclass(frozen=True)
class UnitState:
    """Pure state representation of a game unit.

    No display logic, no UI state - just the facts about this unit.

    stack_index orders units on the same hex (lower = earlier in stack order).
    attributes holds title-defined JSON-safe primitives (shallow-copied on change).
    graphics overrides the key into scenario [[unit_graphics]] when set;
    otherwise unit_type is used (see client DisplayManager).
    """

    unit_id: str
    unit_type: str
    faction: str
    position: Hex
    health: int = 100
    active: bool = True
    stack_index: int = 0
    graphics: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def with_position(self, new_position: Hex) -> UnitState:
        """Return a new UnitState with updated position."""
        return replace(self, position=new_position)

    def with_stack_index(self, stack_index: int) -> UnitState:
        """Return a new UnitState with updated stack order on this hex."""
        return replace(self, stack_index=int(stack_index))

    def with_health(self, new_health: int) -> UnitState:
        """Return a new UnitState with updated health."""
        return replace(self, health=new_health)

    def with_active(self, is_active: bool) -> UnitState:
        """Return a new UnitState with updated active status."""
        return replace(self, active=is_active)

    def with_graphics(self, graphics: str | None) -> UnitState:
        """Return a new UnitState with `graphics` (`[[unit_graphics]]` template key)."""
        return replace(self, graphics=graphics)

    def with_attributes(
        self,
        patch: dict[str, Any] | None = None,
        *,
        remove_keys: tuple[str, ...] | frozenset[str] | None = None,
    ) -> UnitState:
        """Merge patch into attributes; drop keys listed in remove_keys."""
        next_attrs = dict(self.attributes)
        if remove_keys:
            for k in remove_keys:
                next_attrs.pop(k, None)
        if patch:
            next_attrs.update(patch)
        return replace(self, attributes=next_attrs)


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
class BoardEdgeFeature:
    """Rule-neutral primitive on a shared hex side (identity + opaque tags + optional stroke hints)."""

    feature_id: str
    edge_key: EdgeKey
    tags: tuple[str, ...] = ()
    stroke_width: float | None = None
    stroke_color: str | None = None
    stroke_dash: str | None = None
    layer_z: int | None = None


@dataclass(frozen=True)
class BoardLinearFeature:
    """Rule-neutral centerline path through consecutive neighbor hexes."""

    feature_id: str
    path_hexes: tuple[Hex, ...]
    tags: tuple[str, ...] = ()
    stroke_width: float | None = None
    stroke_color: str | None = None
    stroke_dash: str | None = None
    layer_z: int | None = None


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
    edge_features: tuple[BoardEdgeFeature, ...] = ()
    linear_features: tuple[BoardLinearFeature, ...] = ()
    #: Per-tag hex-step cost on `[[linear_features]]` (scenario TOML); sorted by tag.
    linear_movement_by_tag: tuple[tuple[str, float], ...] = ()
    #: Per-tag extra movement cost when a step crosses an `[[edge_features]]` primitive
    #: with that tag (summed per tag occurrence on overlays on that edge). Sorted by tag.
    edge_movement_extra_by_tag: tuple[tuple[str, float], ...] = ()
    #: Per-tag whether crossing an edge with that tag blocks line-of-sight (sorted by tag).
    edge_line_of_sight_by_tag: tuple[tuple[str, bool], ...] = ()

    def edge_map_features_at(self, key: EdgeKey) -> tuple[BoardEdgeFeature, ...]:
        """All edge primitives sharing this undirected border (may be multiple overlays)."""
        return tuple(f for f in self.edge_features if f.edge_key == key)

    def linear_map_features_at_hex(self, h: Hex) -> tuple[BoardLinearFeature, ...]:
        """Centerline primitives whose spine includes this hex."""
        return tuple(f for f in self.linear_features if h in f.path_hexes)

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

    def active_units_at_hex(self, position: Hex) -> tuple[UnitState, ...]:
        """All active units on position, ordered by stack_index then unit_id."""
        found = [u for u in self.units.values() if u.active and u.position == position]
        found.sort(key=lambda u: (u.stack_index, u.unit_id))
        return tuple(found)

    def next_stack_index_at_hex(
        self, position: Hex, *, exclude_unit_id: str | None = None
    ) -> int:
        """Next free stack_index at this hex (max existing + 1 among counted units)."""
        idxs = [
            u.stack_index
            for u in self.units.values()
            if u.active
            and u.position == position
            and (exclude_unit_id is None or u.unit_id != exclude_unit_id)
        ]
        return (max(idxs) + 1) if idxs else 0

    def units_at(self, position: Hex) -> tuple[UnitState, ...]:
        """Alias for active_units_at_hex (stacking-aware)."""
        return self.active_units_at_hex(position)

    def get_unit_at(self, position: Hex) -> UnitState | None:
        """One unit at position for backward compatibility (top of stack = highest stack_index)."""
        at = self.active_units_at_hex(position)
        return at[-1] if at else None

    def is_occupied(self, position: Hex) -> bool:
        """True if any active unit occupies position (stacking-aware)."""
        return bool(self.active_units_at_hex(position))

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
    #: Monotonic counter incremented on each NextPhase apply (time-based title effects).
    global_tick: int = 0

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
        global_tick: int | None = None,
    ) -> TurnState:
        """Return a new TurnState for the next phase.

        If global_tick is None, the tick is unchanged (used when restoring state).
        """
        if global_tick is None:
            return replace(
                self,
                current_faction=new_faction,
                current_phase=new_phase,
                phase_actions_remaining=max_actions,
                schedule_index=schedule_index,
            )
        return replace(
            self,
            current_faction=new_faction,
            current_phase=new_phase,
            phase_actions_remaining=max_actions,
            schedule_index=schedule_index,
            global_tick=int(global_tick),
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

    Title-owned match data lives in ``title_state`` (one bucket per match;
    ``title_bucket_key`` names the pack id). Engine ephemeral data (movement arc,
    etc.) lives in ``engine_state`` (see ``hexengine.state.title_extension``).
    ``rng_log`` is an append-only record of server-authoritative random draws.
    """

    board: BoardState
    turn: TurnState
    title_state: dict[str, Any] = field(default_factory=dict)
    engine_state: dict[str, Any] = field(default_factory=dict)
    title_bucket_key: str | None = None
    rng_log: tuple[dict[str, Any], ...] = ()

    def with_board(self, new_board: BoardState) -> GameState:
        """Return a new GameState with updated board."""
        return replace(self, board=new_board)

    def with_turn(self, new_turn: TurnState) -> GameState:
        """Return a new GameState with updated turn."""
        return replace(self, turn=new_turn)

    def with_title_state(
        self,
        title_state: dict[str, Any],
        *,
        title_bucket_key: str | None = None,
    ) -> GameState:
        """Replace the title-owned bucket (and optionally the pack id key)."""

        kw: dict[str, Any] = {"title_state": dict(title_state)}
        if title_bucket_key is not None:
            kw["title_bucket_key"] = (
                str(title_bucket_key).strip() or None
            )
        return replace(self, **kw)

    def with_engine_state(self, engine_state: dict[str, Any]) -> GameState:
        """Replace engine ephemeral extension entries."""

        return replace(self, engine_state=dict(engine_state))

    def with_title_bucket_key(self, title_bucket_key: str | None) -> GameState:
        """Set the pack id for ``title_state`` (``GameData.title_state_extension_key``)."""

        k = str(title_bucket_key or "").strip() or None
        return replace(self, title_bucket_key=k)

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
                global_tick=0,
            ),
        )
