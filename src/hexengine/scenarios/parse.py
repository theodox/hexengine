"""
Parse scenario files (TOML) into ScenarioData.

No game types or hexengine.map/state imports — only schema and stdlib.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

try:
    import tomllib  # stdlib 3.11+
except ImportError:
    import tomli as tomllib  # fallback for older Python

from .schema import (
    DEFAULT_GLOBAL_BASE_CSS_FILE,
    GlobalStylesConfig,
    LocationRow,
    MapDisplayConfig,
    ScenarioData,
    UnitGraphicsTemplate,
    UnitRow,
)

# Single packaged default: ``data/test_scenario/scenario.toml`` next to this package.
_DEFAULT_PATH = (
    Path(__file__).resolve().parent / "data" / "test_scenario" / "scenario.toml"
)


def default_scenario_path() -> Path:
    """Path to the packaged default scenario TOML (only canonical copy)."""
    return _DEFAULT_PATH


def resolve_scenario_path_for_server() -> Path:
    """
    Path to scenario for game server startup.

    Prefers ``scenarios/<id>/scenario.toml`` or ``scenarios/<name>.toml`` at the
    process current working directory (repo root), then the packaged default.
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
    if isinstance(v, int | float):
        return float(v)
    if isinstance(v, str) and v.strip().lower() in ("inf", "infinity"):
        return float("inf")
    return float(v)


def load_scenario(path: Path | str, *, static_root: Path | None = None) -> ScenarioData:
    """
    Load a scenario from a TOML file. Returns plain ScenarioData.

    ``static_root`` is the directory served as the HTTP site root (defaults to
    ``Path.cwd()``). Used to resolve ``[map].background`` and ``[styles]`` paths
    when files live next to the scenario file.

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
      # optional: assault_modifier, ranged_modifier, block_los, hex_color (e.g. "#338833")

      # Or group many hexes that share terrain / costs (like squads for units):
      [[terrain_groups]]
      terrain = "forest"
      movement_cost = 1.5
      assault_modifier = 0.0
      ranged_modifier = 0.0
      block_los = true
      # optional group hex_color; member rows may set hex_color to override
      members = [
        { position = [5, 5, -10] },
        { position = [6, 4, -10] },
      ]

      [map]
      hex_size = 24
      hex_margin = 0
      hex_stroke = 1
      hex_color = "#33443344"
      terrain_overlay_line_color = "#33443344"
      terrain_overlay_line_width = 2
      background = "assets/map.png"
      unit_size_multiplier = 1.5
      # Optional: fixed hex grid (HexRowCol: i + column, j + row from origin):
      hex_columns = 17
      hex_rows = 7
      # hex_origin_i = 0
      # hex_origin_j = 0

      # Optional global CSS: default base is resources/default/global.css
      [styles]
      # base_css_file = "custom/base.css"   # optional: replace default base
      # css_file = "theme.css"              # optional: after base
      # css = "body { }"                    # optional: last (override)

      # Optional: one primary body per row (svg_file | svg).
      [[unit_graphics]]
      type = "soldier"
      svg_file = "units/soldier.svg"
      render = "image"   # optional: image | inline (for svg_file only)
      css_file = "units/soldier.css"

      [[unit_graphics]]
      type = "badge"
      svg = '''<svg xmlns="http://www.w3.org/2000/svg">...</svg>'''
      css = ".x { fill: red; }"
    """
    path = Path(path).resolve()
    root = (static_root or Path.cwd()).resolve()
    with open(path, "rb") as f:
        data = tomllib.load(f)

    name = str(
        data.get(
            "name", path.parent.name if path.name == "scenario.toml" else path.stem
        )
    )
    description = str(data.get("description", ""))

    map_display = _parse_map_table(data.get("map"), path, root)
    global_styles = _parse_styles_table(data.get("styles"), path, root)
    unit_graphics = _parse_unit_graphics_table(data.get("unit_graphics"), path, root)

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
                hex_color=_optional_nonempty_str(loc, "hex_color"),
            )
        )
    for gi, grp in enumerate(data.get("terrain_groups", [])):
        if not isinstance(grp, dict):
            raise TypeError(
                f"terrain_groups[{gi}] must be a table, got {type(grp).__name__}"
            )
        terrain_type = str(grp.get("terrain", "plain"))
        mc = grp.get("movement_cost", 1.0)
        movement_cost = (
            _float_or_inf(mc) if isinstance(mc, str) else float(mc)
        )
        assault_modifier = float(grp.get("assault_modifier", 0.0))
        ranged_modifier = float(grp.get("ranged_modifier", 0.0))
        block_los = bool(grp.get("block_los", True))
        group_hex_color = _optional_nonempty_str(grp, "hex_color")
        members = grp.get("members", [])
        if not isinstance(members, list):
            raise TypeError(
                f"terrain_groups[{gi}].members must be a list, got {type(members).__name__}"
            )
        for mi, m in enumerate(members):
            if not isinstance(m, dict):
                raise TypeError(
                    f"terrain_groups[{gi}].members[{mi}] must be a table, "
                    f"got {type(m).__name__}"
                )
            if "position" not in m:
                raise ValueError(
                    f"terrain_groups[{gi}].members[{mi}] missing required key 'position'"
                )
            pos = _parse_position(m["position"])
            member_hex_color = _optional_nonempty_str(m, "hex_color")
            hex_color = member_hex_color or group_hex_color
            locations.append(
                LocationRow(
                    position=pos,
                    terrain_type=terrain_type,
                    movement_cost=movement_cost,
                    assault_modifier=assault_modifier,
                    ranged_modifier=ranged_modifier,
                    block_los=block_los,
                    hex_color=hex_color,
                )
            )

    if (
        map_display.hex_columns is not None
        and map_display.hex_rows is not None
    ):
        seen: set[tuple[int, int, int]] = set()
        ordered: list[tuple[int, int, int]] = []
        for loc in locations:
            t = loc.position
            if t not in seen:
                seen.add(t)
                ordered.append(t)
        for u in units:
            t = u.position
            if t not in seen:
                seen.add(t)
                ordered.append(t)
        ordered.sort()
        map_display = replace(map_display, grid_hexes=tuple(ordered))

    return ScenarioData(
        name=name,
        description=description,
        units=units,
        locations=locations,
        map_display=map_display,
        global_styles=global_styles,
        unit_graphics=unit_graphics,
    )


def _parse_styles_table(
    raw: dict | None,
    scenario_toml: Path,
    static_root: Path,
) -> GlobalStylesConfig:
    """
    Parse optional ``[styles]`` table.

    ``base_css_file`` defaults to :data:`DEFAULT_GLOBAL_BASE_CSS_FILE` when omitted.
    ``css_file`` resolves like ``[map].background``.
    """
    r = raw or {}
    base_in = _optional_nonempty_str(r, "base_css_file")
    base_src = base_in if base_in else DEFAULT_GLOBAL_BASE_CSS_FILE
    base_out = resolve_map_background_url(base_src, scenario_toml, static_root)
    css = _optional_nonempty_str(r, "css")
    css_file_in = _optional_nonempty_str(r, "css_file")
    css_file_out = (
        resolve_map_background_url(css_file_in, scenario_toml, static_root)
        if css_file_in
        else None
    )
    return GlobalStylesConfig(
        base_css_file=base_out,
        css=css,
        css_file=css_file_out,
    )


def _optional_nonempty_str(raw: dict, key: str) -> str | None:
    """TOML value as stripped string, or None if missing / blank."""
    if key not in raw:
        return None
    v = raw[key]
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _parse_unit_graphics_table(
    rows: list | None,
    scenario_toml: Path,
    static_root: Path,
) -> dict[str, UnitGraphicsTemplate]:
    """
    Parse ``[[unit_graphics]]`` rows. Each row must set exactly one of
    ``svg_file`` or ``svg``. File paths resolve like ``[map].background``
    (URLs and site-relative paths pass through).
    """
    if not rows:
        return {}
    out: dict[str, UnitGraphicsTemplate] = {}
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise TypeError(
                f"unit_graphics[{i}] must be a table, got {type(row).__name__}"
            )
        unit_type = _optional_nonempty_str(row, "type")
        if not unit_type:
            raise ValueError(f"unit_graphics[{i}] requires non-empty type")

        svg_file_in = _optional_nonempty_str(row, "svg_file")
        svg_in = _optional_nonempty_str(row, "svg")
        primaries = [x for x in (svg_file_in, svg_in) if x is not None]
        if len(primaries) != 1:
            raise ValueError(
                f"unit_graphics[{i}] (type={unit_type!r}) needs exactly one of svg_file, svg"
            )

        css = _optional_nonempty_str(row, "css")
        css_file_in = _optional_nonempty_str(row, "css_file")
        css_file_out = (
            resolve_map_background_url(css_file_in, scenario_toml, static_root)
            if css_file_in
            else None
        )

        render_raw = _optional_nonempty_str(row, "render")

        if svg_file_in is not None:
            svg_file_out = resolve_map_background_url(
                svg_file_in, scenario_toml, static_root
            )
            render = (render_raw or "image").lower()
            if render not in ("image", "inline"):
                raise ValueError(
                    f"unit_graphics[{i}] (type={unit_type!r}): render must be "
                    f"'image' or 'inline' for svg_file, got {render_raw!r}"
                )
            out[unit_type] = UnitGraphicsTemplate(
                unit_type=unit_type,
                render=render,
                svg_file=svg_file_out,
                css=css,
                css_file=css_file_out,
            )
        else:
            assert svg_in is not None
            if render_raw and render_raw.lower() != "inline":
                raise ValueError(
                    f"unit_graphics[{i}] (type={unit_type!r}): inline svg must use "
                    f"render = 'inline' or omit render, got {render_raw!r}"
                )
            out[unit_type] = UnitGraphicsTemplate(
                unit_type=unit_type,
                render="inline",
                svg=svg_in,
                css=css,
                css_file=css_file_out,
            )
    return out


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

    hc_raw = raw.get("hex_columns")
    hr_raw = raw.get("hex_rows")
    hex_columns: int | None = None
    hex_rows: int | None = None
    if hc_raw is not None or hr_raw is not None:
        if hc_raw is None or hr_raw is None:
            raise ValueError(
                "[map] hex_columns and hex_rows must both be set (or both omitted)"
            )
        hex_columns = int(hc_raw)
        hex_rows = int(hr_raw)
        if hex_columns < 1 or hex_rows < 1:
            raise ValueError("[map] hex_columns and hex_rows must be >= 1")

    return MapDisplayConfig(
        hex_size=float(raw.get("hex_size", 24.0)),
        hex_margin=float(raw.get("hex_margin", 0.0)),
        hex_stroke=int(raw.get("hex_stroke", 1)),
        hex_color=str(raw.get("hex_color", "#33443344")),
        background=bg_out,
        unit_size_multiplier=float(raw.get("unit_size_multiplier", 1.5)),
        hex_columns=hex_columns,
        hex_rows=hex_rows,
        hex_origin_i=int(raw.get("hex_origin_i", 0)),
        hex_origin_j=int(raw.get("hex_origin_j", 0)),
        terrain_overlay_line_color=str(
            raw.get("terrain_overlay_line_color", "#33443344")
        ),
        terrain_overlay_line_width=int(raw.get("terrain_overlay_line_width", 2)),
    )
