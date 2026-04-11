"""
Parse scenario files (TOML) into ScenarioData.

TOML ``position`` values are odd-q ``[col, row]`` (see :class:`~hexengine.hexes.types.HexColRow`).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

try:
    import tomllib  # stdlib 3.11+
except ImportError:
    import tomli as tomllib  # fallback for older Python

from ..schema import (
    DEFAULT_GLOBAL_BASE_CSS_FILE,
    GlobalStylesConfig,
    LocationRow,
    MapDisplayConfig,
    MarkerRow,
    ScenarioData,
    UnitGraphicsTemplate,
    UnitRow,
)
from .coercion import coerce_movement_cost, position_to_cube_tuple
from .rows import (
    ensure_dict_table,
    parse_members_list,
    parse_scenario_row,
)

# Packaged default: ``scenarios/data/test_scenario/scenario.toml`` (sibling of ``load/``).
_SCENARIOS_PKG = Path(__file__).resolve().parent.parent
_DEFAULT_PATH = _SCENARIOS_PKG / "data" / "test_scenario" / "scenario.toml"


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
      position = [16, 12]   # odd-q [col, row] (HexColRow)
      faction = "Red"
      # optional: health = 100, active = true

      # Or group repeated type/faction (members can override health/active):
      [[unit_placements]]
      type = "canuck"
      faction = "Red"
      members = [
        { id = "Canuck1", position = [16, 12] },
        { id = "Canuck2", position = [16, 13] },
      ]

      [[locations]]
      position = [5, 7]
      terrain = "forest"
      movement_cost = 1.5
      # optional: assault_modifier, ranged_modifier, block_los, hex_color (e.g. "#338833")

      # Or group many hexes that share terrain / costs (like unit_placements for units):
      [[terrain_groups]]
      terrain = "forest"
      movement_cost = 1.5
      assault_modifier = 0.0
      ranged_modifier = 0.0
      block_los = true
      # optional group hex_color; member rows may set hex_color to override
      members = [
        { position = [5, 7] },
        { position = [6, 7] },
      ]

      [map]
      hex_size = 24
      hex_margin = 0
      hex_stroke = 1
      hex_color = "#33443344"
      terrain_overlay_line_color = "#33443344"
      terrain_overlay_line_width = 2
      background = "assets/map.png"
      # background_crop_to_map = false   # stretch bg to map rect; default true = crop (cover)
      unit_size_multiplier = 1.5
      # Optional: fixed hex grid (axial i + column step, j + row from origin):
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

      # Markers: flat rows or grouped type (like marker_placements; members can override active):
      [[markers]]
      id = "obj-1"
      type = "objective"
      position = [10, 12]

      [[marker_placements]]
      type = "objective"
      # optional: active = true
      members = [
        { id = "obj-2", position = [11, 12] },
      ]
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
    marker_graphics = _parse_unit_graphics_table(
        data.get("marker_graphics"), path, root
    )
    markers = _parse_markers_table(
        data.get("markers")
    ) + _parse_marker_placements_table(data.get("marker_placements"))

    units: list[UnitRow] = []
    for ui, u in enumerate(data.get("units", [])):
        row = ensure_dict_table(u, f"units[{ui}]")
        units.append(parse_scenario_row(UnitRow, row, path=f"units[{ui}]"))

    for si, squad in enumerate(data.get("unit_placements", [])):
        g = ensure_dict_table(squad, f"unit_placements[{si}]")
        unit_type = _optional_nonempty_str(g, "type")
        faction = _optional_nonempty_str(g, "faction")
        if not unit_type:
            raise ValueError(f"unit_placements[{si}] requires non-empty type")
        if not faction:
            raise ValueError(f"unit_placements[{si}] requires non-empty faction")
        squad_health = int(g.get("health", 100))
        squad_active = bool(g.get("active", True))
        members = parse_members_list(
            g.get("members", []), f"unit_placements[{si}].members"
        )
        base = {
            "type": unit_type,
            "faction": faction,
            "health": squad_health,
            "active": squad_active,
        }
        for mi, m in enumerate(members):
            units.append(
                parse_scenario_row(
                    UnitRow,
                    m,
                    path=f"unit_placements[{si}].members[{mi}]",
                    base=base,
                )
            )

    locations: list[LocationRow] = []
    for li, loc in enumerate(data.get("locations", [])):
        row = ensure_dict_table(loc, f"locations[{li}]")
        locations.append(parse_scenario_row(LocationRow, row, path=f"locations[{li}]"))

    for gi, grp in enumerate(data.get("terrain_groups", [])):
        g = ensure_dict_table(grp, f"terrain_groups[{gi}]")
        terrain_type = str(g.get("terrain", "plain"))
        movement_cost = coerce_movement_cost(g.get("movement_cost", 1.0))
        assault_modifier = float(g.get("assault_modifier", 0.0))
        ranged_modifier = float(g.get("ranged_modifier", 0.0))
        block_los = bool(g.get("block_los", True))
        group_hex_color = _optional_nonempty_str(g, "hex_color")
        members = parse_members_list(
            g.get("members", []), f"terrain_groups[{gi}].members"
        )
        base = {
            "terrain": terrain_type,
            "movement_cost": movement_cost,
            "assault_modifier": assault_modifier,
            "ranged_modifier": ranged_modifier,
            "block_los": block_los,
            "hex_color": group_hex_color,
        }
        for mi, m in enumerate(members):
            if "position" not in m:
                raise ValueError(
                    f"terrain_groups[{gi}].members[{mi}] missing required key 'position'"
                )
            member_hex = _optional_nonempty_str(m, "hex_color")
            row_base = dict(base)
            if member_hex is not None:
                row_base["hex_color"] = member_hex
            locations.append(
                parse_scenario_row(
                    LocationRow,
                    m,
                    path=f"terrain_groups[{gi}].members[{mi}]",
                    base=row_base,
                )
            )

    seen: set[tuple[int, int, int]] = set()
    ordered: list[tuple[int, int, int]] = []
    for loc in locations:
        t = position_to_cube_tuple(loc.position)
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    for u in units:
        t = position_to_cube_tuple(u.position)
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    ordered.sort()
    if ordered:
        map_display = replace(map_display, grid_hexes=tuple(ordered))

    return ScenarioData(
        name=name,
        description=description,
        units=units,
        locations=locations,
        map_display=map_display,
        global_styles=global_styles,
        unit_graphics=unit_graphics,
        marker_graphics=marker_graphics,
        markers=markers,
    )


def _parse_markers_table(rows: list | None) -> list[MarkerRow]:
    """Parse ``[[markers]]`` rows: id, type, position, optional active."""
    if not rows:
        return []
    out: list[MarkerRow] = []
    for i, row in enumerate(rows):
        d = ensure_dict_table(row, f"markers[{i}]")
        out.append(parse_scenario_row(MarkerRow, d, path=f"markers[{i}]"))
    return out


def _parse_marker_placements_table(groups: list | None) -> list[MarkerRow]:
    """Parse ``[[marker_placements]]`` rows: shared type, optional default active, members with id/position."""
    if not groups:
        return []
    out: list[MarkerRow] = []
    for gi, grp in enumerate(groups):
        g = ensure_dict_table(grp, f"marker_placements[{gi}]")
        mtype = _optional_nonempty_str(g, "type")
        if not mtype:
            raise ValueError(f"marker_placements[{gi}] requires non-empty type")
        squad_active = bool(g.get("active", True))
        members = parse_members_list(
            g.get("members", []), f"marker_placements[{gi}].members"
        )
        base = {"type": mtype, "active": squad_active}
        for mi, m in enumerate(members):
            if "position" not in m:
                raise ValueError(
                    f"marker_placements[{gi}].members[{mi}] missing required key 'position'"
                )
            out.append(
                parse_scenario_row(
                    MarkerRow,
                    m,
                    path=f"marker_placements[{gi}].members[{mi}]",
                    base=base,
                )
            )
    return out


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
    Parse ``[[unit_graphics]]`` rows.

    - Default: exactly one of ``svg_file`` or ``svg`` (file paths like ``[map].background``).
    - ``render = \"counter\"``: optional ``glyph`` / ``caption``; optional ``counter_fill``,
      ``counter_fill_hover``, ``counter_fill_hilite`` (CSS colors, e.g. ``#c53030``); no SVG asset required.
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

        render_early = _optional_nonempty_str(row, "render")
        if render_early and render_early.lower() == "counter":
            glyph_v = _optional_nonempty_str(row, "glyph")
            cap_raw = row.get("caption")
            cap_v = None if cap_raw is None else str(cap_raw)
            css = _optional_nonempty_str(row, "css")
            css_file_in = _optional_nonempty_str(row, "css_file")
            css_file_out = (
                resolve_map_background_url(css_file_in, scenario_toml, static_root)
                if css_file_in
                else None
            )
            out[unit_type] = UnitGraphicsTemplate(
                unit_type=unit_type,
                render="counter",
                glyph=glyph_v,
                caption=cap_v,
                css=css,
                css_file=css_file_out,
                counter_fill=_optional_nonempty_str(row, "counter_fill"),
                counter_fill_hover=_optional_nonempty_str(row, "counter_fill_hover"),
                counter_fill_hilite=_optional_nonempty_str(row, "counter_fill_hilite"),
            )
            continue

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

    bg_crop_raw = raw.get("background_crop_to_map")
    background_crop_to_map = (
        MapDisplayConfig.background_crop_to_map
        if bg_crop_raw is None
        else bool(bg_crop_raw)
    )

    return MapDisplayConfig(
        hex_size=float(raw.get("hex_size", 24.0)),
        hex_margin=float(raw.get("hex_margin", 0.0)),
        hex_stroke=int(raw.get("hex_stroke", 1)),
        hex_color=str(raw.get("hex_color", "#33443344")),
        background=bg_out,
        background_crop_to_map=background_crop_to_map,
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
