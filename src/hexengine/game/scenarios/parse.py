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

# Packaged default: folder layout scenarios/data/<id>/scenario.toml
_DEFAULT_PATH = (
    Path(__file__).resolve().parent / "data" / "test_scenario" / "scenario.toml"
)


def default_scenario_path() -> Path:
    """Path to the packaged default scenario TOML."""
    return _DEFAULT_PATH


def resolve_scenario_path_for_server() -> Path:
    """
    Path to scenario for game server startup.

    Prefers a scenario folder: scenarios/<id>/scenario.toml, then legacy flat
    scenarios/<name>.toml, then packaged default.
    """
    cwd = Path.cwd()
    candidates = [
        cwd / "scenarios" / "test_scenario" / "scenario.toml",
        cwd / "scenarios" / "test_scenario.toml",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return default_scenario_path()


def resolve_map_background_url(
    background: str,
    scenario_toml: Path,
    static_root: Path,
) -> str:
    """
    Turn [map].background into a URL path for the browser static server.

    - http(s):// or root-relative (/...) are returned unchanged.
    - If ``background`` is relative and ``(scenario_toml.parent / background)``
      exists, return that file's path relative to ``static_root`` (POSIX slashes).
    - Otherwise return ``background`` with backslashes normalized (site-root-relative
      paths like resources/map.png).
    """
    bg = (background or "").strip()
    if not bg:
        return MapDisplayConfig.background
    low = bg.lower()
    if low.startswith("http://") or low.startswith("https://") or bg.startswith("/"):
        return bg
    p = Path(bg)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(static_root.resolve()).as_posix()
        except ValueError:
            return bg.replace("\\", "/")
    candidate = (scenario_toml.parent / p).resolve()
    if candidate.is_file():
        try:
            return candidate.relative_to(static_root.resolve()).as_posix()
        except ValueError:
            return bg.replace("\\", "/")
    return bg.replace("\\", "/")


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


def load_scenario(path: Path | str, *, static_root: Path | None = None) -> ScenarioData:
    """
    Load a scenario from a TOML file. Returns plain ScenarioData.

    ``static_root`` is the directory served as the HTTP site root (defaults to
    ``Path.cwd()``). Used to resolve ``[map].background`` when the file lives next
    to the scenario file.

    TOML shape:
      name = "..."
      description = "..."

      [[units]]
      id = "Canuck1"
      type = "canuck"
      position = [16, 4, -20]
      faction = "Red"
      # optional: health = 100, active = true

      # Or group repeated type/faction (members can override health/active):
      [[squads]]
      type = "canuck"
      faction = "Red"
      members = [
        { id = "Canuck1", position = [16, 4, -20] },
        { id = "Canuck2", position = [16, 5, -21] },
      ]

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
      background = "assets/map.png"
      unit_size_multiplier = 1.5
    """
    path = Path(path).resolve()
    root = (static_root or Path.cwd()).resolve()
    with open(path, "rb") as f:
        data = tomllib.load(f)

    name = str(data.get("name", path.parent.name if path.name == "scenario.toml" else path.stem))
    description = str(data.get("description", ""))

    map_display = _parse_map_table(data.get("map"), path, root)

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
    for squad in data.get("squads", []):
        unit_type = str(squad["type"])
        faction = str(squad["faction"])
        squad_health = int(squad.get("health", 100))
        squad_active = bool(squad.get("active", True))
        for m in squad.get("members", []):
            pos = _parse_position(m["position"])
            units.append(
                UnitRow(
                    unit_id=str(m["id"]),
                    unit_type=unit_type,
                    position=pos,
                    faction=faction,
                    health=int(m.get("health", squad_health)),
                    active=bool(m.get("active", squad_active)),
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


def _parse_map_table(
    raw: dict | None,
    scenario_toml: Path,
    static_root: Path,
) -> MapDisplayConfig:
    """Parse optional [map] TOML table; missing keys use MapDisplayConfig defaults."""
    if not raw:
        return MapDisplayConfig()
    bg_in = str(raw.get("background", MapDisplayConfig.background))
    bg_out = resolve_map_background_url(bg_in, scenario_toml, static_root)
    return MapDisplayConfig(
        hex_size=float(raw.get("hex_size", 24.0)),
        hex_margin=float(raw.get("hex_margin", 0.0)),
        hex_stroke=int(raw.get("hex_stroke", 1)),
        hex_color=str(raw.get("hex_color", "#33443344")),
        background=bg_out,
        unit_size_multiplier=float(raw.get("unit_size_multiplier", 1.5)),
    )
