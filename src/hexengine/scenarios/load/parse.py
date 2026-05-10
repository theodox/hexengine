"""
Parse scenario files (TOML) into ScenarioData.

TOML `position` values are odd-q `[col, row]` (see `hexengine.hexes.types.HexColRow`).
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from ..schema import ColorRow, ScenarioData
from .color_palette import apply_scenario_color_constants
from .coercion import coerce_movement_cost
from .map_parse import (
    _load_scenario_map_pieces,
    _merge_sparse_grid_hexes,
    resolve_map_background_url,
)
from .rows import ensure_dict_table, parse_scenario_row
from .units_parse import _load_scenario_units, _load_unit_archetypes

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


def _canonical_linear_movement(
    costs: dict[str, float],
) -> tuple[tuple[str, float], ...]:
    return tuple(sorted(costs.items(), key=lambda kv: kv[0]))


def _parse_linear_movement(data: dict[str, Any]) -> tuple[tuple[str, float], ...]:
    """
    ``[linear_movement]`` table (tag keys) and/or ``[[linear_movement]]`` rows.

    Omitted tags have no linear override; titles use the destination hex terrain cost.
    """
    out: dict[str, float] = {}
    raw = data.get("linear_movement")
    if isinstance(raw, dict):
        for k, v in raw.items():
            tag = str(k).strip()
            if not tag:
                raise ValueError("linear_movement: empty tag key is not allowed")
            if tag in out:
                raise ValueError(f"linear_movement: duplicate tag {tag!r}")
            out[tag] = coerce_movement_cost(v)
    elif isinstance(raw, list):
        for i, row in enumerate(raw):
            if not isinstance(row, dict):
                raise TypeError(
                    f"linear_movement[{i}] must be a table, got {type(row).__name__}"
                )
            tag_raw = row.get("tag")
            if tag_raw is None:
                raise ValueError(f"linear_movement[{i}] requires key 'tag'")
            tag = str(tag_raw).strip()
            if not tag:
                raise ValueError(f"linear_movement[{i}]: tag must be non-empty")
            if tag in out:
                raise ValueError(f"linear_movement[{i}]: duplicate tag {tag!r}")
            if "movement_cost" not in row:
                raise ValueError(f"linear_movement[{i}] requires key 'movement_cost'")
            out[tag] = coerce_movement_cost(row["movement_cost"])
    elif raw is not None:
        raise TypeError(
            f"linear_movement must be a table or array of tables, got {type(raw).__name__}"
        )

    return _canonical_linear_movement(out)


def _canonical_edge_movement_extra(
    costs: dict[str, float],
) -> tuple[tuple[str, float], ...]:
    return tuple(sorted(costs.items(), key=lambda kv: kv[0]))


def _parse_edge_movement_extra(data: dict[str, Any]) -> tuple[tuple[str, float], ...]:
    """
    ``[edge_movement_extra]`` table (tag keys) and/or ``[[edge_movement_extra]]`` rows.

    Omitted tags add no extra cost when crossing an edge with that tag.
    """
    out: dict[str, float] = {}
    raw = data.get("edge_movement_extra")
    if isinstance(raw, dict):
        for k, v in raw.items():
            tag = str(k).strip()
            if not tag:
                raise ValueError("edge_movement_extra: empty tag key is not allowed")
            if tag in out:
                raise ValueError(f"edge_movement_extra: duplicate tag {tag!r}")
            out[tag] = coerce_movement_cost(v)
    elif isinstance(raw, list):
        for i, row in enumerate(raw):
            if not isinstance(row, dict):
                raise TypeError(
                    f"edge_movement_extra[{i}] must be a table, got {type(row).__name__}"
                )
            tag_raw = row.get("tag")
            if tag_raw is None:
                raise ValueError(f"edge_movement_extra[{i}] requires key 'tag'")
            tag = str(tag_raw).strip()
            if not tag:
                raise ValueError(f"edge_movement_extra[{i}]: tag must be non-empty")
            if tag in out:
                raise ValueError(f"edge_movement_extra[{i}]: duplicate tag {tag!r}")
            if "movement_extra" not in row:
                raise ValueError(f"edge_movement_extra[{i}] requires key 'movement_extra'")
            out[tag] = coerce_movement_cost(row["movement_extra"])
    elif raw is not None:
        raise TypeError(
            f"edge_movement_extra must be a table or array of tables, got {type(raw).__name__}"
        )

    return _canonical_edge_movement_extra(out)


def _canonical_edge_line_of_sight(flags: dict[str, bool]) -> tuple[tuple[str, bool], ...]:
    return tuple(sorted(flags.items(), key=lambda kv: kv[0]))


def _parse_edge_line_of_sight(data: dict[str, Any]) -> tuple[tuple[str, bool], ...]:
    """
    ``[edge_line_of_sight]`` table (tag keys → bool) and/or ``[[edge_line_of_sight]]`` rows.

    Only tags mapped to true block LOS when a sight line crosses an edge feature carrying
    that tag.
    """
    out: dict[str, bool] = {}
    raw = data.get("edge_line_of_sight")
    if isinstance(raw, dict):
        for k, v in raw.items():
            tag = str(k).strip()
            if not tag:
                raise ValueError("edge_line_of_sight: empty tag key is not allowed")
            if tag in out:
                raise ValueError(f"edge_line_of_sight: duplicate tag {tag!r}")
            out[tag] = bool(v)
    elif isinstance(raw, list):
        for i, row in enumerate(raw):
            if not isinstance(row, dict):
                raise TypeError(
                    f"edge_line_of_sight[{i}] must be a table, got {type(row).__name__}"
                )
            tag_raw = row.get("tag")
            if tag_raw is None:
                raise ValueError(f"edge_line_of_sight[{i}] requires key 'tag'")
            tag = str(tag_raw).strip()
            if not tag:
                raise ValueError(f"edge_line_of_sight[{i}]: tag must be non-empty")
            if tag in out:
                raise ValueError(f"edge_line_of_sight[{i}]: duplicate tag {tag!r}")
            if "blocks" not in row:
                raise ValueError(f"edge_line_of_sight[{i}] requires key 'blocks'")
            out[tag] = bool(row["blocks"])
    elif raw is not None:
        raise TypeError(
            f"edge_line_of_sight must be a table or array of tables, got {type(raw).__name__}"
        )

    return _canonical_edge_line_of_sight(out)


def _load_scenario_constants(data: dict[str, Any]) -> tuple[ColorRow, ...]:
    """Expand `@color` placeholders in raw TOML values; return parsed ``[[colors]]`` rows."""
    apply_scenario_color_constants(data)
    return _parse_colors_table(data.get("colors"))


def load_scenario(path: Path | str, *, static_root: Path | None = None) -> ScenarioData:
    """
    Load a scenario from a TOML file. Returns plain ScenarioData.

    # @TODO: remove the long comment here and clean up api

    `static_root` is the directory served as the HTTP site root (defaults to
    `Path.cwd()`). Used to resolve `[map].background`, `[styles]`, and
    `[[unit_graphics]]` file paths. For `.../scenarios/<id>/scenario.toml`, relative
    paths without `..` are resolved under `<pack>/resources/` first when that folder
    exists, then under the scenario directory.

    TOML shape:
      name = "..."
      description = "..."
      # optional: per-tag hex-step cost on [[linear_features]] (roads, rails, …):
      #   [linear_movement]
      #   road = 0.5
      #   rail = 0.33
      # or repeated rows:
      #   [[linear_movement]]
      #   tag = "road"
      #   movement_cost = 0.5
      #
      # optional: [[edge_features]] tag rules (same tag strings as on primitives):
      #   [edge_movement_extra]
      #   river = 1.0
      #   [[edge_movement_extra]]
      #   tag = "river"
      #   movement_extra = 1.0
      #   [edge_line_of_sight]
      #   river = true
      #   [[edge_line_of_sight]]
      #   tag = "river"
      #   blocks = true

      [[units]]
      id = "Canuck1"
      type = "canuck"
      position = [16, 12]   # odd-q [col, row] (HexColRow)
      faction = "Red"
      # optional: health = 100, active = true
      # optional: graphics = "soldier"   # [[unit_graphics]] key; defaults to type

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
      # optional: health, active, id_prefix, graphics (override via unit_placements too)

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

    colors = _load_scenario_constants(data)

    name = str(
        data.get(
            "name", path.parent.name if path.name == "scenario.toml" else path.stem
        )
    )
    description = str(data.get("description", ""))
    schema_version = int(data.get("schema_version", 1))
    linear_movement_by_tag = _parse_linear_movement(data)
    edge_movement_extra_by_tag = _parse_edge_movement_extra(data)
    edge_line_of_sight_by_tag = _parse_edge_line_of_sight(data)

    archetype_by_name = _load_unit_archetypes(data)
    units = _load_scenario_units(data, archetype_by_name)
    mp = _load_scenario_map_pieces(data, path, root)
    map_display = _merge_sparse_grid_hexes(mp.map_display, mp.locations, units)

    return ScenarioData(
        name=name,
        description=description,
        schema_version=schema_version,
        colors=colors,
        units=units,
        locations=mp.locations,
        terrain_types=mp.terrain_types,
        map_display=map_display,
        global_styles=mp.global_styles,
        unit_graphics=mp.unit_graphics,
        marker_graphics=mp.marker_graphics,
        markers=mp.markers,
        edge_features=mp.edge_features,
        linear_features=mp.linear_features,
        linear_movement_by_tag=linear_movement_by_tag,
        edge_movement_extra_by_tag=edge_movement_extra_by_tag,
        edge_line_of_sight_by_tag=edge_line_of_sight_by_tag,
    )


__all__ = [
    "default_scenario_path",
    "load_scenario",
    "resolve_map_background_url",
]
