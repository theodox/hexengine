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


@dataclass(frozen=True)
class MapDisplayConfig:
    """Map / board presentation from scenario (no Pyodide or DOM)."""

    hex_size: float = 24.0
    hex_margin: float = 0.0
    hex_stroke: int = 1
    hex_color: str = "#33443344"
    background: str = "resources/test_map.png"
    unit_size_multiplier: float = 1.5

    def to_wire_dict(self) -> dict:
        """Stable keys for JSON StateUpdate (matches field names)."""
        return {
            "hex_size": self.hex_size,
            "hex_margin": self.hex_margin,
            "hex_stroke": self.hex_stroke,
            "hex_color": self.hex_color,
            "background": self.background,
            "unit_size_multiplier": self.unit_size_multiplier,
        }

    @classmethod
    def from_wire_dict(cls, d: dict) -> "MapDisplayConfig":
        return cls(
            hex_size=float(d.get("hex_size", 24.0)),
            hex_margin=float(d.get("hex_margin", 0.0)),
            hex_stroke=int(d.get("hex_stroke", 1)),
            hex_color=str(d.get("hex_color", "#33443344")),
            background=str(d.get("background", "resources/test_map.png")),
            unit_size_multiplier=float(d.get("unit_size_multiplier", 1.5)),
        )


@dataclass
class ScenarioData:
    """Parsed scenario: name, description, and rows. No game imports."""

    name: str
    description: str = ""
    units: list[UnitRow] = field(default_factory=list)
    locations: list[LocationRow] = field(default_factory=list)
    map_display: MapDisplayConfig = field(default_factory=MapDisplayConfig)
