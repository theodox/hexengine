"""
Scenario data schema: plain data only, no game types.

This is the stable "DSL" representation. When game classes change
(UnitState, LocationState, LocationItem, etc.), only the loader
that maps this schema onto those types needs to change.
"""

from dataclasses import dataclass, field


# Position as (i, j, k) so we don't depend on hexengine.hexes here.
# Loader converts to Hex when building game objects.
Position = tuple[int, int, int]


@dataclass(frozen=True)
class UnitRow:
    """One unit from a scenario file. No Python class references."""

    unit_id: str
    unit_type: str  # e.g. "canuck", "soldier" — loader maps to game class or action
    position: Position
    faction: str
    health: int = 100
    active: bool = True


@dataclass(frozen=True)
class LocationRow:
    """One terrain location from a scenario file."""

    position: Position
    terrain_type: str
    movement_cost: float
    assault_modifier: float = 0.0
    ranged_modifier: float = 0.0
    block_los: bool = True


@dataclass
class ScenarioData:
    """Parsed scenario: name, description, and rows. No game imports."""

    name: str
    description: str = ""
    units: list[UnitRow] = field(default_factory=list)
    locations: list[LocationRow] = field(default_factory=list)
