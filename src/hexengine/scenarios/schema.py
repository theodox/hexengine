"""
Scenario data schema: plain data only, no game types.

This is the stable "DSL" representation. When game classes change
(UnitState, LocationState, etc.), only the loader
that maps this schema onto those types needs to change.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, fields
from typing import Any, TypeVar

# Odd-q offset ``(col, row)`` as in TOML ``position = [col, row]`` (see ``HexColRow``).
Position = tuple[int, int]

ST = TypeVar("ST")


def toml_field(
    toml_key: str,
    *,
    nonempty: bool = False,
    coerce: str | None = None,
    optional_str: bool = False,
) -> dict[str, Any]:
    """
    Metadata for :func:`~hexengine.scenarios.load.rows.parse_scenario_row`.

    - ``nonempty``: strip string; reject blank (required TOML string fields).
    - ``coerce``: registered name (e.g. ``\"position\"``, ``\"movement_cost\"``).
    - ``optional_str``: strip; empty or missing uses field default (often ``None``).
    """
    m: dict[str, Any] = {"toml_key": toml_key}
    if nonempty:
        m["nonempty"] = True
    if coerce is not None:
        m["coerce"] = coerce
    if optional_str:
        m["optional_str"] = True
    return m


def scenario_toml_table(table_name: str) -> Callable[[type[ST]], type[ST]]:
    """Declare the TOML array name for this row type (errors / tooling)."""

    def deco(cls: type[ST]) -> type[ST]:
        cls.__scenario_toml_table__ = table_name  # type: ignore[attr-defined]
        return cls

    return deco


def _dataclass_to_wire_dict(
    obj: object,
    *,
    rename: dict[str, str] | None = None,
    omit_none: bool = False,
    value_transforms: dict[str, Callable[[Any], Any]] | None = None,
) -> dict[str, Any]:
    """
    Serialize a dataclass instance to a JSON-friendly dict by walking ``fields(obj)``.

    - ``rename``: Python field name → wire key (e.g. ``unit_type`` → ``type``).
    - ``omit_none``: drop keys whose value is ``None`` after optional transforms.
    - ``value_transforms``: per *Python* field name; run on the attribute value
      (``None`` is passed through without calling the transform).
    """
    rename = rename or {}
    value_transforms = value_transforms or {}
    out: dict[str, Any] = {}
    for f in fields(obj):
        val = getattr(obj, f.name)
        tr = value_transforms.get(f.name)
        if tr is not None:
            val = tr(val)
        if omit_none and val is None:
            continue
        out[rename.get(f.name, f.name)] = val
    return out


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
        return _dataclass_to_wire_dict(self, omit_none=True)

    @classmethod
    def from_wire_dict(cls, d: dict) -> GlobalStylesConfig:
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


@scenario_toml_table("units")
@dataclass(frozen=True)
class UnitRow:
    """One unit from a scenario file. No Python class references."""

    unit_id: str = field(metadata=toml_field("id", nonempty=True))
    unit_type: str = field(
        metadata=toml_field("type", nonempty=True)
    )  # e.g. "canuck", "soldier"
    #: Odd-q ``(col, row)`` after parse (same as :class:`~hexengine.hexes.types.HexColRow`).
    position: Position = field(metadata=toml_field("position", coerce="position"))
    faction: str = field(metadata=toml_field("faction", nonempty=True))
    health: int = field(default=100, metadata=toml_field("health"))
    active: bool = field(default=True, metadata=toml_field("active"))


@scenario_toml_table("locations")
@dataclass(frozen=True)
class LocationRow:
    """One terrain location from a scenario file."""

    #: Odd-q ``(col, row)`` after parse (same as :class:`~hexengine.hexes.types.HexColRow`).
    position: Position = field(metadata=toml_field("position", coerce="position"))
    terrain_type: str = field(default="plain", metadata=toml_field("terrain"))
    movement_cost: float = field(
        default=1.0, metadata=toml_field("movement_cost", coerce="movement_cost")
    )
    assault_modifier: float = field(
        default=0.0, metadata=toml_field("assault_modifier")
    )
    ranged_modifier: float = field(default=0.0, metadata=toml_field("ranged_modifier"))
    block_los: bool = field(default=True, metadata=toml_field("block_los"))
    #: Optional CSS-style hex for terrain overlay (e.g. ``#RRGGBB`` or ``#RRGGBBAA``).
    hex_color: str | None = field(
        default=None, metadata=toml_field("hex_color", optional_str=True)
    )


@dataclass(frozen=True)
class MapDisplayConfig:
    """Map / board presentation from scenario (no Pyodide or DOM)."""

    hex_size: float = 24.0
    hex_margin: float = 0.0
    hex_stroke: int = 1
    hex_color: str = "#33443344"
    background: str = "resources/test_map.png"
    #: When True, ``#map-bg`` uses CSS ``background-size: cover`` (crop to map rect); when
    #: False, ``background-size: 100% 100%`` stretches the image to the rect.
    background_crop_to_map: bool = True
    unit_size_multiplier: float = 1.5
    # Fixed grid in cube coordinates: columns = i step, rows = j step (axial rectangle).
    # When both are set, the client sizes the canvas/SVG to this grid; when None, legacy
    # “fill the CSS canvas box” behavior.
    hex_columns: int | None = None
    hex_rows: int | None = None
    hex_origin_i: int = 0
    hex_origin_j: int = 0
    #: When set with ``hex_columns`` / ``hex_rows``, canvas bounds and grid lines use this
    #: occupied set instead of the full axis-aligned rectangle (sparse Hextml-style maps).
    grid_hexes: tuple[tuple[int, int, int], ...] | None = None
    #: Terrain tint canvas stroke (CSS color, e.g. ``#RRGGBB`` / ``#RRGGBBAA``).
    terrain_overlay_line_color: str = "#33443344"
    terrain_overlay_line_width: int = 2

    def to_wire_dict(self) -> dict:
        """Stable keys for JSON StateUpdate (matches field names)."""
        return _dataclass_to_wire_dict(
            self,
            omit_none=True,
            value_transforms={
                "grid_hexes": lambda gh: [list(t) for t in gh]
                if gh is not None
                else None,
            },
        )

    @classmethod
    def from_wire_dict(cls, d: dict) -> MapDisplayConfig:
        hc = d.get("hex_columns")
        hr = d.get("hex_rows")
        if hc is None and hr is None:
            cols: int | None = None
            rows: int | None = None
        else:
            cols = int(hc) if hc is not None else None
            rows = int(hr) if hr is not None else None
            if cols is None or rows is None or cols < 1 or rows < 1:
                cols, rows = None, None
        raw_gh = d.get("grid_hexes")
        grid_hexes: tuple[tuple[int, int, int], ...] | None = None
        if raw_gh is not None:
            if not isinstance(raw_gh, list):
                raise TypeError("map_display.grid_hexes must be a list of [i,j,k]")
            triples: list[tuple[int, int, int]] = []
            for i, item in enumerate(raw_gh):
                if not isinstance(item, list | tuple) or len(item) != 3:
                    raise ValueError(
                        f"map_display.grid_hexes[{i}] must be [i, j, k], got {item!r}"
                    )
                triples.append((int(item[0]), int(item[1]), int(item[2])))
            grid_hexes = tuple(triples)
        return cls(
            hex_size=float(d.get("hex_size", 24.0)),
            hex_margin=float(d.get("hex_margin", 0.0)),
            hex_stroke=int(d.get("hex_stroke", 1)),
            hex_color=str(d.get("hex_color", "#33443344")),
            background=str(d.get("background", "resources/test_map.png")),
            background_crop_to_map=(
                True
                if (v := d.get("background_crop_to_map", True)) is None
                else bool(v)
            ),
            unit_size_multiplier=float(d.get("unit_size_multiplier", 1.5)),
            hex_columns=cols,
            hex_rows=rows,
            hex_origin_i=int(d.get("hex_origin_i", 0)),
            hex_origin_j=int(d.get("hex_origin_j", 0)),
            grid_hexes=grid_hexes,
            terrain_overlay_line_color=str(
                d.get("terrain_overlay_line_color", "#33443344")
            ),
            terrain_overlay_line_width=int(d.get("terrain_overlay_line_width", 2)),
        )


@dataclass(frozen=True)
class UnitGraphicsTemplate:
    """
    Per-unit-type presentation from scenario (no DOM).

    For SVG assets: exactly one of ``svg_file`` or ``svg`` is set after parse.
    ``render`` is ``image`` / ``inline`` for ``svg_file``, or ``inline`` for embedded ``svg``.

    For ``render`` = ``counter``, use optional ``glyph`` / ``caption`` strings instead of SVG.
    Optional ``counter_fill`` / ``counter_fill_hover`` / ``counter_fill_hilite`` set CSS custom
    properties on the unit (same names as ``resources/default/unit_counter.css`` fallbacks).
    """

    unit_type: str
    render: str = "image"
    svg_file: str | None = None
    svg: str | None = None
    css: str | None = None
    css_file: str | None = None
    glyph: str | None = None
    caption: str | None = None
    counter_fill: str | None = None
    counter_fill_hover: str | None = None
    counter_fill_hilite: str | None = None

    def to_wire_dict(self) -> dict:
        """JSON-safe keys for StateUpdate (``type`` matches TOML / unit rows)."""
        return _dataclass_to_wire_dict(
            self,
            rename={"unit_type": "type"},
            omit_none=True,
        )


@scenario_toml_table("markers")
@dataclass(frozen=True)
class MarkerRow:
    """One marker instance from a scenario file (phase 1: non-interactive)."""

    marker_id: str = field(metadata=toml_field("id", nonempty=True))
    marker_type: str = field(metadata=toml_field("type", nonempty=True))
    position: Position = field(metadata=toml_field("position", coerce="position"))
    active: bool = field(default=True, metadata=toml_field("active"))

    def to_wire_dict(self) -> dict[str, Any]:
        """Marker payload for StateUpdate (odd-q ``position`` as ``[col, row]``)."""
        return _dataclass_to_wire_dict(
            self,
            rename={"marker_id": "id", "marker_type": "type"},
            value_transforms={
                "position": lambda p: [int(p[0]), int(p[1])],
            },
        )


@dataclass
class ScenarioData:
    """Parsed scenario: name, description, and rows. No game imports."""

    name: str
    description: str = ""
    units: list[UnitRow] = field(default_factory=list)
    locations: list[LocationRow] = field(default_factory=list)
    map_display: MapDisplayConfig = field(default_factory=MapDisplayConfig)
    global_styles: GlobalStylesConfig = field(
        default_factory=default_global_styles_unresolved
    )
    unit_graphics: dict[str, UnitGraphicsTemplate] = field(default_factory=dict)
    # marker_graphics + markers mirror unit_graphics + units: type → template, then instances.
    marker_graphics: dict[str, UnitGraphicsTemplate] = field(default_factory=dict)
    markers: list[MarkerRow] = field(default_factory=list)

    def unit_graphics_to_wire_dict(self) -> dict[str, dict]:
        """Map unit type string → template payload for JSON sync."""
        return {k: v.to_wire_dict() for k, v in self.unit_graphics.items()}

    def marker_graphics_to_wire_dict(self) -> dict[str, dict]:
        """Map marker type string → template payload for JSON sync."""
        return {k: v.to_wire_dict() for k, v in self.marker_graphics.items()}

    def markers_to_wire_list(self) -> list[dict]:
        """Marker instances for JSON sync."""
        return [m.to_wire_dict() for m in self.markers]
