"""
Parse scenario files (TOML) into ScenarioData.

No game types or hexengine.map/state imports — only schema and stdlib.
"""

from pathlib import Path

try:
    import tomllib  # stdlib 3.11+
except ImportError:
    import tomli as tomllib  # fallback for older Python

from .schema import LocationRow, MapDisplayConfig, ScenarioData, UnitRow

# Default scenario path (package data); override by passing a path to load_scenario().
_DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "test_scenario.toml"


def default_scenario_path() -> Path:
    """Path to the packaged default scenario TOML."""
    return _DEFAULT_PATH


def resolve_scenario_path_for_server() -> Path:
    """
    Path to scenario for game server startup: project scenarios/ if present,
    else packaged default (same rule as websocket_server.main).
    """
    root = Path.cwd() / "scenarios" / "test_scenario.toml"
    if root.exists():
        return root
    return default_scenario_path()


def _parse_position(raw: list[int] | tuple[int, ...]) -> tuple[int, int, int]:
    """Convert [i, j, k] or (i, j, k) to (i, j, k). Validates length."""
    if len(raw) != 3:
        raise ValueError(f"position must have 3 elements (i, j, k), got {len(raw)}")
    return (int(raw[0]), int(raw[1]), int(raw[2]))


def _float_or_inf(v: str | float) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str) and v.strip().lower() in ("inf", "infinity"):
        return float("inf")
    return float(v)


def load_scenario(path: Path | str) -> ScenarioData:
    """
    Load a scenario from a TOML file. Returns plain ScenarioData.

    TOML shape:
      name = "..."
      description = "..."

      [[units]]
      id = "Canuck1"
      type = "canuck"
      position = [16, 4, -20]
      faction = "Red"
      # optional: health = 100, active = true

      [[locations]]
      position = [5, 5, -10]
      terrain = "forest"
      movement_cost = 1.5
      # optional: assault_modifier, ranged_modifier, block_los

      [map]
      hex_size = 24
      hex_margin = 0
      hex_stroke = 1
      hex_color = "#33443344"
      background = "resources/test_map.png"
      unit_size_multiplier = 1.5
    """
    path = Path(path)
    with open(path, "rb") as f:
        data = tomllib.load(f)

    name = str(data.get("name", path.stem))
    description = str(data.get("description", ""))

    map_display = _parse_map_table(data.get("map"))

    units: list[UnitRow] = []
    for u in data.get("units", []):
        pos = _parse_position(u["position"])
        units.append(
            UnitRow(
                unit_id=str(u["id"]),
                unit_type=str(u["type"]),
                position=pos,
                faction=str(u["faction"]),
                health=int(u.get("health", 100)),
                active=bool(u.get("active", True)),
            )
        )

    locations: list[LocationRow] = []
    for loc in data.get("locations", []):
        pos = _parse_position(loc["position"])
        mc = loc.get("movement_cost", 1.0)
        locations.append(
            LocationRow(
                position=pos,
                terrain_type=str(loc.get("terrain", "plain")),
                movement_cost=_float_or_inf(mc) if isinstance(mc, str) else float(mc),
                assault_modifier=float(loc.get("assault_modifier", 0.0)),
                ranged_modifier=float(loc.get("ranged_modifier", 0.0)),
                block_los=bool(loc.get("block_los", True)),
            )
        )

    return ScenarioData(
        name=name,
        description=description,
        units=units,
        locations=locations,
        map_display=map_display,
    )


def _parse_map_table(raw: dict | None) -> MapDisplayConfig:
    """Parse optional [map] TOML table; missing keys use MapDisplayConfig defaults."""
    if not raw:
        return MapDisplayConfig()
    return MapDisplayConfig(
        hex_size=float(raw.get("hex_size", 24.0)),
        hex_margin=float(raw.get("hex_margin", 0.0)),
        hex_stroke=int(raw.get("hex_stroke", 1)),
        hex_color=str(raw.get("hex_color", "#33443344")),
        background=str(raw.get("background", "resources/test_map.png")),
        unit_size_multiplier=float(raw.get("unit_size_multiplier", 1.5)),
    )
