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

# Site-relative path served with the static root (see [styles] in scenario TOML).
DEFAULT_GLOBAL_BASE_CSS_FILE = "resources/default/global.css"


@dataclass(frozen=True)
class GlobalStylesConfig:
    """
    App-wide CSS: a base stylesheet plus optional scenario layers.

    The base sheet loads first; ``css_file`` and ``css`` follow (cascade / override).
    """

    base_css_file: str
    css: str | None = None
    css_file: str | None = None

    def to_wire_dict(self) -> dict:
        """JSON-safe dict for StateUpdate."""
        d: dict = {"base_css_file": self.base_css_file}
        if self.css is not None:
            d["css"] = self.css
        if self.css_file is not None:
            d["css_file"] = self.css_file
        return d

    @classmethod
    def from_wire_dict(cls, d: dict) -> "GlobalStylesConfig":
        raw_css = d.get("css")
        raw_cf = d.get("css_file")
        return cls(
            base_css_file=str(d.get("base_css_file", DEFAULT_GLOBAL_BASE_CSS_FILE)),
            css=None if raw_css is None else str(raw_css),
            css_file=None if raw_cf is None else str(raw_cf),
        )


def default_global_styles_unresolved() -> GlobalStylesConfig:
    """Default before ``load_scenario`` resolution (matches packaged / repo layout)."""
    return GlobalStylesConfig(base_css_file=DEFAULT_GLOBAL_BASE_CSS_FILE)


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


@dataclass(frozen=True)
class UnitGraphicsTemplate:
    """
    Per-unit-type presentation from scenario (no DOM).

    Exactly one of ``svg_file`` or ``svg`` is set after parse.
    ``render`` is ``image`` / ``inline`` for ``svg_file``, or ``inline`` for embedded ``svg``.
    """

    unit_type: str
    render: str = "image"
    svg_file: str | None = None
    svg: str | None = None
    css: str | None = None
    css_file: str | None = None

    def to_wire_dict(self) -> dict:
        """JSON-safe keys for StateUpdate (``type`` matches TOML / unit rows)."""
        d: dict = {"type": self.unit_type, "render": self.render}
        if self.svg_file is not None:
            d["svg_file"] = self.svg_file
        if self.svg is not None:
            d["svg"] = self.svg
        if self.css is not None:
            d["css"] = self.css
        if self.css_file is not None:
            d["css_file"] = self.css_file
        return d


@dataclass
class ScenarioData:
    """Parsed scenario: name, description, and rows. No game imports."""

    name: str
    description: str = ""
    units: list[UnitRow] = field(default_factory=list)
    locations: list[LocationRow] = field(default_factory=list)
    map_display: MapDisplayConfig = field(default_factory=MapDisplayConfig)
    global_styles: GlobalStylesConfig = field(default_factory=default_global_styles_unresolved)
    unit_graphics: dict[str, UnitGraphicsTemplate] = field(default_factory=dict)

    def unit_graphics_to_wire_dict(self) -> dict[str, dict]:
        """Map unit type string → template payload for JSON sync."""
        return {k: v.to_wire_dict() for k, v in self.unit_graphics.items()}
