"""Terrain, map display, styles, graphics, markers, and edge/linear features."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from ..schema import (
    DEFAULT_GLOBAL_BASE_CSS_FILE,
    EdgeEndpointSpec,
    EdgeFeatureSpec,
    GlobalStylesConfig,
    LinearFeatureSpec,
    LocationRow,
    MapDisplayConfig,
    MarkerRow,
    TerrainTypeRow,
    UnitGraphicsTemplate,
    UnitRow,
)
from .coercion import coerce_movement_cost, position_to_cube_tuple
from .parse_common import _optional_nonempty_str
from .rows import ensure_dict_table, parse_positions_list, parse_scenario_row


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


@dataclass(frozen=True)
class _ScenarioMapPieces:
    """Parsed terrain, presentation, and vector map primitives (pre grid_hexes merge)."""

    terrain_types: tuple[TerrainTypeRow, ...]
    locations: list[LocationRow]
    map_display: MapDisplayConfig
    global_styles: GlobalStylesConfig
    unit_graphics: dict[str, UnitGraphicsTemplate]
    marker_graphics: dict[str, UnitGraphicsTemplate]
    markers: list[MarkerRow]
    edge_features: tuple[EdgeFeatureSpec, ...]
    linear_features: tuple[LinearFeatureSpec, ...]


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


def _col_row_cell(cell: object, *, ctx: str) -> tuple[int, int]:
    """One odd-q waypoint as `[col, row]`."""
    if not isinstance(cell, list | tuple) or len(cell) != 2:
        raise ValueError(f"{ctx} must be [col, row]")
    return (int(cell[0]), int(cell[1]))


def _parse_tags_list(raw: object, path: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise TypeError(f"{path}: tags must be a list of strings")
    out: list[str] = []
    for i, x in enumerate(raw):
        if not isinstance(x, str) or not str(x).strip():
            raise ValueError(f"{path}[{i}] must be a non-empty string")
        out.append(str(x).strip())
    return tuple(out)


def _parse_edge_endpoint(raw: object, pfx: str) -> EdgeEndpointSpec:
    d = ensure_dict_table(raw, pfx)
    between_raw = d.get("between")
    pos_raw = d.get("position")
    dir_raw = d.get("direction")
    has_b = between_raw is not None
    has_pd = pos_raw is not None or dir_raw is not None
    if has_b and has_pd:
        raise ValueError(
            f"{pfx}: use either between = [[col,row],[col,row]] or position + direction, not both"
        )
    if not has_b and not has_pd:
        raise ValueError(
            f"{pfx}: requires between = [[col, row], [col, row]] or position = [col, row] and direction"
        )
    if has_b:
        if not isinstance(between_raw, list) or len(between_raw) != 2:
            raise ValueError(f"{pfx}.between must be a list of two [col, row] entries")
        pair = tuple(
            _col_row_cell(cell, ctx=f"{pfx}.between[{j}]")
            for j, cell in enumerate(between_raw)
        )
        return EdgeEndpointSpec(between=(pair[0], pair[1]))
    if pos_raw is None or dir_raw is None:
        raise ValueError(f"{pfx}: position and direction must both be set")
    if not isinstance(pos_raw, list | tuple) or len(pos_raw) != 2:
        raise ValueError(f"{pfx}.position must be [col, row]")
    return EdgeEndpointSpec(
        position=(int(pos_raw[0]), int(pos_raw[1])),
        direction=int(dir_raw),
    )


def _optional_stroke_color(d: dict[str, Any]) -> str | None:
    """TOML `stroke_color` or shorthand `color` (CSS/SVG stroke value, e.g. #4a90d9)."""
    raw = d.get("stroke_color")
    if raw is None:
        raw = d.get("color")
    if raw is None:
        return None
    s = str(raw).strip()
    return s if s else None


def _parse_map_feature_style_fields(
    d: dict[str, Any],
) -> tuple[float | None, str | None, str | None, int | None]:
    """Shared optional stroke / z-order keys for [[edge_features]] and [[linear_features]]."""
    sw = d.get("stroke_width")
    stroke_width = None if sw is None else float(sw)
    stroke_color = _optional_stroke_color(d)
    sd = d.get("stroke_dash")
    stroke_dash = None if sd is None else (s if (s := str(sd).strip()) else None)
    lz = d.get("layer_z")
    layer_z = None if lz is None else int(lz)
    return stroke_width, stroke_color, stroke_dash, layer_z


def _feature_id_from_row(d: dict[str, Any], *, fallback: str) -> str:
    raw_fid = d.get("feature_id")
    if raw_fid is not None and str(raw_fid).strip():
        return str(raw_fid).strip()
    return fallback


def _raise_on_duplicate_strings(values: Sequence[str], *, label: str) -> None:
    seen: set[str] = set()
    for v in values:
        if v in seen:
            raise ValueError(f"duplicate {label} {v!r}")
        seen.add(v)


def _parse_waypoints_continuation(raw: object, pfx: str) -> tuple[tuple[int, int], ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise TypeError(f"{pfx}.waypoints must be a list of [col, row]")
    return tuple(
        _col_row_cell(cell, ctx=f"{pfx}.waypoints[{j}]") for j, cell in enumerate(raw)
    )


def _parse_edge_features_table(raw: object) -> tuple[EdgeFeatureSpec, ...]:
    if raw is None or raw == []:
        return ()
    if not isinstance(raw, list):
        raise TypeError(f"edge_features must be a list, got {type(raw).__name__}")
    out: list[EdgeFeatureSpec] = []
    for i, row in enumerate(raw):
        pfx = f"edge_features[{i}]"
        d = ensure_dict_table(row, pfx)
        for bad_key in ("between", "position", "direction"):
            if d.get(bad_key) is not None:
                raise ValueError(
                    f"{pfx}: put {bad_key!r} inside start_edge or end_edge "
                    f"(inline table), not on the [[edge_features]] row"
                )
        se_raw = d.get("start_edge")
        if se_raw is None:
            raise ValueError(
                f"{pfx}: requires start_edge = {{ between = [...] }} or "
                f"{{ position = [...], direction = ... }}; optional end_edge and waypoints"
            )
        start_edge = _parse_edge_endpoint(se_raw, f"{pfx}.start_edge")
        ee_raw = d.get("end_edge")
        end_edge = (
            _parse_edge_endpoint(ee_raw, f"{pfx}.end_edge")
            if ee_raw is not None
            else None
        )
        waypoints_norm = _parse_waypoints_continuation(d.get("waypoints"), pfx)
        feature_id = _feature_id_from_row(d, fallback=f"edge-{i}")
        tags = _parse_tags_list(d.get("tags"), f"{pfx}.tags")
        stroke_width, stroke_color, stroke_dash, layer_z = (
            _parse_map_feature_style_fields(d)
        )
        ss_raw = d.get("start_side")
        start_side = None if ss_raw is None else int(ss_raw)
        es_raw = d.get("end_side")
        end_side = None if es_raw is None else int(es_raw)
        out.append(
            EdgeFeatureSpec(
                feature_id=feature_id,
                start_edge=start_edge,
                waypoints=waypoints_norm,
                end_edge=end_edge,
                tags=tags,
                stroke_width=stroke_width,
                stroke_color=stroke_color,
                stroke_dash=stroke_dash,
                layer_z=layer_z,
                start_side=start_side,
                end_side=end_side,
            )
        )
    _raise_on_duplicate_strings(
        [s.feature_id for s in out], label="edge_features feature_id"
    )
    return tuple(out)


def _parse_col_row_point_list(
    raw: object, pfx: str, key: str
) -> tuple[tuple[int, int], ...]:
    if not isinstance(raw, list) or len(raw) < 2:
        raise ValueError(
            f"{pfx}.{key} must be a list of at least two [col, row] points"
        )
    return tuple(
        _col_row_cell(cell, ctx=f"{pfx}.{key}[{j}]") for j, cell in enumerate(raw)
    )


def _parse_linear_features_table(raw: object) -> tuple[LinearFeatureSpec, ...]:
    if raw is None or raw == []:
        return ()
    if not isinstance(raw, list):
        raise TypeError(f"linear_features must be a list, got {type(raw).__name__}")
    out: list[LinearFeatureSpec] = []
    for i, row in enumerate(raw):
        pfx = f"linear_features[{i}]"
        d = ensure_dict_table(row, pfx)
        path_raw = d.get("path")
        perim_raw = d.get("perimeter_of")
        wp_raw = d.get("waypoints")
        has_path = path_raw is not None and path_raw != []
        has_perim = perim_raw is not None and perim_raw != []
        has_wp = wp_raw is not None and wp_raw != []
        modes = int(has_path) + int(has_perim) + int(has_wp)
        if modes != 1:
            raise ValueError(
                f"{pfx}: specify exactly one of 'path', 'perimeter_of', or 'waypoints'"
            )
        path_pts: tuple[tuple[int, int], ...] | None = None
        perim_pts: tuple[tuple[int, int], ...] | None = None
        wp_pts: tuple[tuple[int, int], ...] | None = None
        if has_path:
            path_pts = _parse_col_row_point_list(path_raw, pfx, "path")
        elif has_perim:
            perim_pts = _parse_col_row_point_list(perim_raw, pfx, "perimeter_of")
        else:
            wp_pts = _parse_col_row_point_list(wp_raw, pfx, "waypoints")
        feature_id = _feature_id_from_row(d, fallback=f"linear-{i}")
        tags = _parse_tags_list(d.get("tags"), f"{pfx}.tags")
        stroke_width, stroke_color, stroke_dash, layer_z = (
            _parse_map_feature_style_fields(d)
        )
        out.append(
            LinearFeatureSpec(
                feature_id=feature_id,
                path=path_pts,
                perimeter_of=perim_pts,
                waypoints=wp_pts,
                tags=tags,
                stroke_width=stroke_width,
                stroke_color=stroke_color,
                stroke_dash=stroke_dash,
                layer_z=layer_z,
            )
        )
    _raise_on_duplicate_strings(
        [s.feature_id for s in out], label="linear_features feature_id"
    )
    return tuple(out)


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


def _resolved_css_file_href(
    row: dict[str, Any],
    scenario_toml: Path,
    static_root: Path,
) -> str | None:
    """Resolve optional `css_file` on a row the same way as `[styles].css_file`."""
    css_file_in = _optional_nonempty_str(row, "css_file")
    if not css_file_in:
        return None
    return resolve_map_background_url(css_file_in, scenario_toml, static_root)


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
    css_file_out = _resolved_css_file_href(r, scenario_toml, static_root)
    return GlobalStylesConfig(
        base_css_file=base_out,
        css=css,
        css_file=css_file_out,
    )


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
            css_file_out = _resolved_css_file_href(row, scenario_toml, static_root)
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
        css_file_out = _resolved_css_file_href(row, scenario_toml, static_root)

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


def _load_scenario_map_pieces(
    data: dict[str, Any],
    scenario_toml: Path,
    static_root: Path,
) -> _ScenarioMapPieces:
    """Terrain, locations, `[map]` / styles / graphics / markers / edge & linear features."""
    terrain_types = _parse_terrain_types(data.get("terrain_types"))
    terrain_by_type = {t.terrain_type: t for t in terrain_types}

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

    map_display = _parse_map_table(data.get("map"), scenario_toml, static_root)
    global_styles = _parse_styles_table(data.get("styles"), scenario_toml, static_root)
    unit_graphics = _parse_unit_graphics_table(
        data.get("unit_graphics"), scenario_toml, static_root
    )
    marker_graphics = _parse_unit_graphics_table(
        data.get("marker_graphics"), scenario_toml, static_root
    )
    markers = _parse_markers_table(
        data.get("markers")
    ) + _parse_marker_placements_table(data.get("marker_placements"))
    edge_features = _parse_edge_features_table(data.get("edge_features"))
    linear_features = _parse_linear_features_table(data.get("linear_features"))

    return _ScenarioMapPieces(
        terrain_types=terrain_types,
        locations=locations,
        map_display=map_display,
        global_styles=global_styles,
        unit_graphics=unit_graphics,
        marker_graphics=marker_graphics,
        markers=markers,
        edge_features=edge_features,
        linear_features=linear_features,
    )


def _merge_sparse_grid_hexes(
    map_display: MapDisplayConfig,
    locations: list[LocationRow],
    units: list[UnitRow],
) -> MapDisplayConfig:
    """When `[map]` omits fixed dimensions, shrink the canvas to occupied odd-q hexes."""
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
    if ordered and (map_display.hex_columns is None or map_display.hex_rows is None):
        return replace(map_display, grid_hexes=tuple(ordered))
    return map_display
