"""
Parse scenario files (TOML) into ScenarioData.

TOML `position` values are odd-q `[col, row]` (see `hexengine.hexes.types.HexColRow`).
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Any

try:
    import tomllib  # stdlib 3.11+
except ImportError:
    import tomli as tomllib  # fallback for older Python

from ..schema import (
    DEFAULT_GLOBAL_BASE_CSS_FILE,
    ColorRow,
    GlobalStylesConfig,
    LocationRow,
    MapDisplayConfig,
    MarkerRow,
    ScenarioData,
    TerrainTypeRow,
    UnitArchetypeRow,
    UnitGraphicsTemplate,
    UnitRow,
)
from .coercion import coerce_movement_cost, position_to_cube_tuple
from .color_palette import apply_scenario_color_constants
from .rows import (
    ensure_dict_table,
    parse_positions_list,
    parse_scenario_row,
)

# Packaged default: `scenarios/data/test_scenario/scenario.toml` (sibling of `load/`).
_SCENARIOS_PKG = Path(__file__).resolve().parent.parent
_DEFAULT_PATH = _SCENARIOS_PKG / "data" / "test_scenario" / "scenario.toml"


def _raise_toml_decode_with_context(
    path: Path, source: str, exc: BaseException
) -> None:
    """Re-raise TOML parse failures with path, line text, and column caret."""
    msg = str(exc)
    m = re.search(r"line (\d+), column (\d+)", msg, flags=re.IGNORECASE)
    lines = source.splitlines()
    parts = [
        f"TOML syntax error while loading scenario file: {path}",
        f"Parser message: {msg}",
    ]
    if m:
        line_no = int(m.group(1))
        col_no = int(m.group(2))
        if 1 <= line_no <= len(lines):
            prefix = f"Line {line_no}: "
            line_text = lines[line_no - 1]
            parts.append(prefix + line_text)
            if col_no >= 1:
                pad = len(prefix) + col_no - 1
                parts.append(f"{' ' * pad}^ (column {col_no})")
        else:
            parts.append(
                f"(File has {len(lines)} lines; parser reported line {line_no})"
            )
    raise ValueError("\n".join(parts)) from exc


def _load_scenario_toml(path: Path) -> dict[str, Any]:
    """Load UTF-8 scenario TOML; `ValueError` includes offending source line on failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Could not read scenario file: {path} ({e})") from e
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        _raise_toml_decode_with_context(path, text, e)


def default_scenario_path() -> Path:
    """Path to the packaged default scenario TOML (only canonical copy)."""
    return _DEFAULT_PATH


def _pack_resources_dir(scenario_toml: Path) -> Path | None:
    """
    Game packs often use `<pack>/scenarios/<id>/scenario.toml` with shared assets in
    `<pack>/resources/`. When that directory exists, relative paths without `..`
    resolve there first (then fall back to the scenario folder).
    """
    try:
        p = scenario_toml.resolve()
    except OSError:
        p = scenario_toml
    scenarios_dir = p.parent.parent
    if scenarios_dir.name != "scenarios":
        return None
    r = scenarios_dir.parent / "resources"
    try:
        return r if r.is_dir() else None
    except OSError:
        return None


def resolve_map_background_url(
    background: str,
    scenario_toml: Path,
    static_root: Path,
) -> str:
    """
    Turn [map].background into a URL path for the browser static server.

    - http(s):// or root-relative (/...) are returned unchanged.
    - If `background` is relative, without `..` path segments, and the scenario
      lives under `.../scenarios/<id>/scenario.toml` with a sibling `resources/`
      directory, try `(resources / background)` first.
    - Else if `(scenario_toml.parent / background)` exists, return that path relative
      to `static_root` (POSIX slashes).
    - Otherwise return `background` with backslashes normalized (site-root-relative
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

    static = static_root.resolve()
    pr = _pack_resources_dir(scenario_toml)
    if pr is not None and ".." not in p.parts:
        try:
            base = pr.resolve()
            candidate = (pr / p).resolve()
            candidate.relative_to(base)
        except (OSError, ValueError):
            pass
        else:
            if candidate.is_file():
                try:
                    return candidate.relative_to(static).as_posix()
                except ValueError:
                    return bg.replace("\\", "/")

    try:
        candidate = (scenario_toml.parent / p).resolve()
    except OSError:
        return bg.replace("\\", "/")
    if candidate.is_file():
        try:
            return candidate.relative_to(static).as_posix()
        except ValueError:
            return bg.replace("\\", "/")
    return bg.replace("\\", "/")


def load_scenario(path: Path | str, *, static_root: Path | None = None) -> ScenarioData:
    """
    Load a scenario from a TOML file. Returns plain ScenarioData.

    `static_root` is the directory served as the HTTP site root (defaults to
    `Path.cwd()`). Used to resolve `[map].background`, `[styles]`, and
    `[[unit_graphics]]` file paths. For `.../scenarios/<id>/scenario.toml`, relative
    paths without `..` are resolved under `<pack>/resources/` first when that folder
    exists, then under the scenario directory.

    TOML shape:
      name = "..."
      description = "..."

      [[units]]
      id = "Canuck1"
      type = "canuck"
      position = [16, 12]   # odd-q [col, row] (HexColRow)
      faction = "Red"
      # optional: health = 100, active = true

      # Or group repeated type/faction (position rows can override health/active).
      # Omit `id` on a row to auto-assign a unique id (prefix `type-faction`):
      [[unit_placements]]
      type = "canuck"
      faction = "Red"
      positions = [
        [16, 12],
        { id = "Canuck2", position = [16, 13] },
      ]

      # Named archetypes (optional): `[[unit_archetypes]]` or `[[unit_archetype]]`.
      # Reference from unit_placements with `archetype = "..."`.
      [[unit_archetypes]]
      name = "red_line"
      type = "soldier"
      faction = "Red"
      # optional: health, active, id_prefix = "red_line"   # default id prefix is name

      [[unit_placements]]
      archetype = "red_line"
      positions = [ [0, 0], [1, 0] ]

      # Optional named CSS colors; reference elsewhere as @name (word boundary, not x@y).
      # Style A — repeated rows:
      [[colors]]
      name = "woods_fill"
      value = "rgba(88, 196, 93, 0.75)"

      [[colors]]
      name = "stream_fill"
      value = "rgba(23, 83, 188, 0.9)"

      # Style B — one flat table (less boilerplate; key order matters for @ between entries):
      [colors]
      woods_fill = "rgba(88, 196, 93, 0.75)"
      stream_fill = "rgba(23, 83, 188, 0.9)"

      # Required: exactly one row with default = true (used for hexes not listed in groups):
      [[terrain_types]]
      terrain = "open_ground"
      movement_cost = 1.0
      default = true
      hex_color = "@woods_fill"

      # Or group many hexes that share terrain / costs (like unit_placements for units):
      [[terrain_groups]]
      terrain = "forest"
      movement_cost = 1.5
      assault_modifier = 0.0
      ranged_modifier = 0.0
      block_los = true
      # optional group hex_color; position rows may set hex_color to override.
      # Plain coordinates may be bare [col, row] pairs:
      positions = [ [5, 7], [6, 7] ]

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
      # Optional: fixed hex grid in odd-q HexColRow (col, row), same as unit positions:
      hex_columns = 17
      hex_rows = 7
      # hex_origin_col = 0   # or legacy hex_origin_i
      # hex_origin_row = 0   # or legacy hex_origin_j

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

      # Markers: flat rows or grouped type (position rows can override active):
      [[markers]]
      id = "obj-1"
      type = "objective"
      position = [10, 12]

      [[marker_placements]]
      type = "objective"
      # optional: active = true
      positions = [
        { id = "obj-2", position = [11, 12] },
      ]
    """
    path = Path(path).resolve()
    root = (static_root or Path.cwd()).resolve()
    data = _load_scenario_toml(path)

    apply_scenario_color_constants(data)

    name = str(
        data.get(
            "name", path.parent.name if path.name == "scenario.toml" else path.stem
        )
    )
    description = str(data.get("description", ""))
    schema_version = int(data.get("schema_version", 1))

    map_display = _parse_map_table(data.get("map"), path, root)
    global_styles = _parse_styles_table(data.get("styles"), path, root)
    unit_graphics = _parse_unit_graphics_table(data.get("unit_graphics"), path, root)
    marker_graphics = _parse_unit_graphics_table(
        data.get("marker_graphics"), path, root
    )
    markers = _parse_markers_table(
        data.get("markers")
    ) + _parse_marker_placements_table(data.get("marker_placements"))

    terrain_types = _parse_terrain_types(data.get("terrain_types"))
    terrain_by_type = {t.terrain_type: t for t in terrain_types}

    _archetype_rows: list = []
    _u_arch = data.get("unit_archetypes")
    _u_arch1 = data.get("unit_archetype")
    if isinstance(_u_arch, list):
        _archetype_rows.extend(_u_arch)
    if isinstance(_u_arch1, list):
        _archetype_rows.extend(_u_arch1)
    archetype_by_name = _parse_unit_archetype_index(
        _archetype_rows if _archetype_rows else None
    )

    units: list[UnitRow] = []
    used_unit_ids: set[str] = set()
    auto_unit_id_counters: dict[str, int] = {}

    for ui, u in enumerate(data.get("units", [])):
        row = ensure_dict_table(u, f"units[{ui}]")
        ur = parse_scenario_row(UnitRow, row, path=f"units[{ui}]")
        if ur.unit_id in used_unit_ids:
            raise ValueError(f"units[{ui}] duplicate unit id {ur.unit_id!r}")
        used_unit_ids.add(ur.unit_id)
        units.append(ur)

    for si, squad in enumerate(data.get("unit_placements", [])):
        g = ensure_dict_table(squad, f"unit_placements[{si}]")
        arch = _optional_nonempty_str(g, "archetype")
        explicit_type = _optional_nonempty_str(g, "type")
        explicit_faction = _optional_nonempty_str(g, "faction")
        if arch:
            if explicit_type is not None or explicit_faction is not None:
                raise ValueError(
                    f"unit_placements[{si}] must not set both archetype and type/faction"
                )
            if arch not in archetype_by_name:
                raise ValueError(
                    f"unit_placements[{si}] references unknown archetype {arch!r}"
                )
            ar = archetype_by_name[arch]
            unit_type = ar.unit_type
            faction = ar.faction
            squad_health = int(g.get("health", ar.health))
            squad_active = bool(g.get("active", ar.active))
            id_prefix = (ar.id_prefix or ar.name).strip()
        else:
            if not explicit_type:
                raise ValueError(
                    f"unit_placements[{si}] requires non-empty type or archetype"
                )
            if not explicit_faction:
                raise ValueError(
                    f"unit_placements[{si}] requires non-empty faction or use archetype"
                )
            unit_type = explicit_type
            faction = explicit_faction
            squad_health = int(g.get("health", 100))
            squad_active = bool(g.get("active", True))
            id_prefix = f"{unit_type}-{faction}"
        if "positions" not in g:
            raise ValueError(
                f"unit_placements[{si}] requires key 'positions' (list of placement tables)"
            )
        pos_rows = parse_positions_list(
            g["positions"], f"unit_placements[{si}].positions"
        )
        base = {
            "type": unit_type,
            "faction": faction,
            "health": squad_health,
            "active": squad_active,
        }
        for pi, m in enumerate(pos_rows):
            row = dict(m)
            raw_id = row.get("id")
            has_id = raw_id is not None and str(raw_id).strip() != ""
            if not has_id:
                row["id"] = _allocate_auto_unit_id(
                    used_unit_ids, id_prefix, auto_unit_id_counters
                )
            else:
                uid = str(raw_id).strip()
                if uid in used_unit_ids:
                    raise ValueError(
                        f"unit_placements[{si}].positions[{pi}] duplicate unit id {uid!r}"
                    )
            ur = parse_scenario_row(
                UnitRow,
                row,
                path=f"unit_placements[{si}].positions[{pi}]",
                base=base,
            )
            if ur.unit_id in used_unit_ids:
                raise ValueError(
                    f"unit_placements[{si}].positions[{pi}] duplicate unit id {ur.unit_id!r}"
                )
            used_unit_ids.add(ur.unit_id)
            units.append(ur)

    locations: list[LocationRow] = []
    for gi, grp in enumerate(data.get("terrain_groups", [])):
        g = ensure_dict_table(grp, f"terrain_groups[{gi}]")
        terrain_type = str(g.get("terrain", "plain"))
        tt = terrain_by_type.get(terrain_type)
        base = _terrain_group_location_base(g, terrain_type, tt)
        if "positions" not in g:
            raise ValueError(
                f"terrain_groups[{gi}] requires key 'positions' (list of placement tables)"
            )
        pos_rows = parse_positions_list(
            g["positions"], f"terrain_groups[{gi}].positions"
        )
        for pi, m in enumerate(pos_rows):
            if "position" not in m:
                raise ValueError(
                    f"terrain_groups[{gi}].positions[{pi}] missing required key 'position'"
                )
            member_hex = _optional_nonempty_str(m, "hex_color")
            row_base = dict(base)
            if member_hex is not None:
                row_base["hex_color"] = member_hex
            locations.append(
                parse_scenario_row(
                    LocationRow,
                    m,
                    path=f"terrain_groups[{gi}].positions[{pi}]",
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
    # Tight canvas for sparse maps: only when [map] omits hex_columns/hex_rows. If both
    # dimensions are set, the client draws the full axial rectangle; sparse grid_hexes
    # would shrink the board to occupied hexes only (wrong for e.g. 6×6 skirmish maps).
    if ordered and (map_display.hex_columns is None or map_display.hex_rows is None):
        map_display = replace(map_display, grid_hexes=tuple(ordered))

    colors = _parse_colors_table(data.get("colors"))

    return ScenarioData(
        name=name,
        description=description,
        schema_version=schema_version,
        colors=colors,
        units=units,
        locations=locations,
        terrain_types=terrain_types,
        map_display=map_display,
        global_styles=global_styles,
        unit_graphics=unit_graphics,
        marker_graphics=marker_graphics,
        markers=markers,
    )


def _parse_colors_table(raw: object) -> tuple[ColorRow, ...]:
    """
    Parse colors after `hexengine.scenarios.load.color_palette.apply_scenario_color_constants`.

    Accepts the normalized list of `{name, value}` rows (from `[[colors]]` or `[colors]`).
    """
    if raw is None or raw == []:
        return ()
    if not isinstance(raw, list):
        raise TypeError(f"colors must be a list, got {type(raw).__name__}")
    rows: list[ColorRow] = []
    for i, item in enumerate(raw):
        d = ensure_dict_table(item, f"colors[{i}]")
        rows.append(parse_scenario_row(ColorRow, d, path=f"colors[{i}]"))
    return tuple(rows)


def _parse_terrain_types(raw: object) -> tuple[TerrainTypeRow, ...]:
    """
    Parse `[[terrain_types]]` rows. Exactly one row must have `default = true`;
    that row defines terrain for hexes not listed under `[[terrain_groups]]`.
    """
    if raw is None or raw == []:
        raise ValueError(
            "scenario must declare at least one [[terrain_types]] row; "
            "exactly one must set default = true"
        )
    if not isinstance(raw, list):
        raise TypeError(f"terrain_types must be a list, got {type(raw).__name__}")
    rows: list[TerrainTypeRow] = []
    for ti, item in enumerate(raw):
        d = ensure_dict_table(item, f"terrain_types[{ti}]")
        rows.append(parse_scenario_row(TerrainTypeRow, d, path=f"terrain_types[{ti}]"))
    defaults = [r for r in rows if r.is_default]
    if len(defaults) != 1:
        raise ValueError(
            "scenario must declare exactly one [[terrain_types]] with default = true "
            f"(found {len(defaults)})"
        )
    return tuple(rows)


def _terrain_group_location_base(
    g: dict[str, Any], terrain_type: str, tt: TerrainTypeRow | None
) -> dict[str, Any]:
    """Values for each explicit hex: `[[terrain_types]]` row matching `terrain`, overridden by keys on `g`."""
    if "movement_cost" in g:
        movement_cost = coerce_movement_cost(g["movement_cost"])
    elif tt is not None:
        movement_cost = tt.movement_cost
    else:
        movement_cost = coerce_movement_cost(1.0)

    if "assault_modifier" in g:
        assault_modifier = float(g["assault_modifier"])
    elif tt is not None:
        assault_modifier = tt.assault_modifier
    else:
        assault_modifier = 0.0

    if "ranged_modifier" in g:
        ranged_modifier = float(g["ranged_modifier"])
    elif tt is not None:
        ranged_modifier = tt.ranged_modifier
    else:
        ranged_modifier = 0.0

    if "block_los" in g:
        block_los = bool(g["block_los"])
    elif tt is not None:
        block_los = tt.block_los
    else:
        block_los = True

    if "hex_color" in g:
        group_hex_color = _optional_nonempty_str(g, "hex_color")
    elif tt is not None:
        group_hex_color = tt.hex_color
    else:
        group_hex_color = None

    return {
        "terrain": terrain_type,
        "movement_cost": movement_cost,
        "assault_modifier": assault_modifier,
        "ranged_modifier": ranged_modifier,
        "block_los": block_los,
        "hex_color": group_hex_color,
    }


def _parse_markers_table(rows: list | None) -> list[MarkerRow]:
    """Parse `[[markers]]` rows: id, type, position, optional active."""
    if not rows:
        return []
    out: list[MarkerRow] = []
    for i, row in enumerate(rows):
        d = ensure_dict_table(row, f"markers[{i}]")
        out.append(parse_scenario_row(MarkerRow, d, path=f"markers[{i}]"))
    return out


def _parse_marker_placements_table(groups: list | None) -> list[MarkerRow]:
    """Parse `[[marker_placements]]` rows: shared type, optional default active, positions with id/position."""
    if not groups:
        return []
    out: list[MarkerRow] = []
    for gi, grp in enumerate(groups):
        g = ensure_dict_table(grp, f"marker_placements[{gi}]")
        mtype = _optional_nonempty_str(g, "type")
        if not mtype:
            raise ValueError(f"marker_placements[{gi}] requires non-empty type")
        squad_active = bool(g.get("active", True))
        if "positions" not in g:
            raise ValueError(
                f"marker_placements[{gi}] requires key 'positions' (list of placement tables)"
            )
        pos_rows = parse_positions_list(
            g["positions"], f"marker_placements[{gi}].positions"
        )
        base = {"type": mtype, "active": squad_active}
        for pi, m in enumerate(pos_rows):
            if "position" not in m:
                raise ValueError(
                    f"marker_placements[{gi}].positions[{pi}] missing required key 'position'"
                )
            out.append(
                parse_scenario_row(
                    MarkerRow,
                    m,
                    path=f"marker_placements[{gi}].positions[{pi}]",
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
    Parse optional `[styles]` table.

    `base_css_file` defaults to `DEFAULT_GLOBAL_BASE_CSS_FILE` when omitted.
    `css_file` resolves like `[map].background`.
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


def _unit_id_token(prefix: str) -> str:
    """Normalize a string for use inside auto-generated unit `id` values."""
    t = re.sub(r"[^a-zA-Z0-9_-]+", "_", prefix.strip())
    return t.strip("_") or "unit"


def _allocate_auto_unit_id(
    used: set[str], prefix: str, counters: dict[str, int]
) -> str:
    """Next `{token}-{n}` not in `used` (increments per token)."""
    base = _unit_id_token(prefix)
    while True:
        n = counters.get(base, 0) + 1
        counters[base] = n
        cand = f"{base}-{n}"
        if cand not in used:
            return cand


def _parse_unit_archetype_index(raw: object) -> dict[str, UnitArchetypeRow]:
    if raw is None or raw == []:
        return {}
    if not isinstance(raw, list):
        raise TypeError(f"unit_archetypes must be a list, got {type(raw).__name__}")
    out: dict[str, UnitArchetypeRow] = {}
    for i, item in enumerate(raw):
        d = ensure_dict_table(item, f"unit_archetypes[{i}]")
        row = parse_scenario_row(UnitArchetypeRow, d, path=f"unit_archetypes[{i}]")
        if row.name in out:
            raise ValueError(f"duplicate unit_archetypes name {row.name!r}")
        out[row.name] = row
    return out


def _parse_unit_graphics_table(
    rows: list | None,
    scenario_toml: Path,
    static_root: Path,
) -> dict[str, UnitGraphicsTemplate]:
    """
    Parse `[[unit_graphics]]` rows.

    - Default: exactly one of `svg_file` or `svg` (file paths like `[map].background`).
    - `render = "counter"`: optional `glyph` / `caption`; optional `counter_fill`,
      `counter_fill_hover`, `counter_fill_hilite` (CSS colors, e.g. `#c53030`); no SVG asset required.
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
        hex_origin_i=int(raw.get("hex_origin_col", raw.get("hex_origin_i", 0))),
        hex_origin_j=int(raw.get("hex_origin_row", raw.get("hex_origin_j", 0))),
        terrain_overlay_line_color=str(
            raw.get("terrain_overlay_line_color", "#33443344")
        ),
        terrain_overlay_line_width=int(raw.get("terrain_overlay_line_width", 2)),
    )
