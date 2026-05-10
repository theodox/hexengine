"""Unit and unit-archetype rows from scenario TOML."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from ..schema import UnitArchetypeRow, UnitRow
from .parse_common import _optional_nonempty_str
from .rows import (
    coerce_unit_attributes,
    ensure_dict_table,
    parse_positions_list,
    parse_scenario_row,
)

_UNIT_ARCHETYPE_RESERVED_TOML_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "type",
        "graphics",
        "faction",
        "health",
        "active",
        "id_prefix",
        "attributes",
    }
)


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


def _normalize_unit_archetype_row_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
    """
    Allow flat keys on [[unit_archetype]] / [[unit_archetypes]] rows
    (e.g. combat = 6) as shorthand for attributes.

    An explicit attributes = { ... } table is merged first; duplicate keys from
    flat entries override the table (flat wins).
    """
    d = dict(raw)
    explicit_attrs = coerce_unit_attributes(d.pop("attributes", None))
    flat_attrs: dict[str, Any] = {}
    for key in list(d.keys()):
        if key in _UNIT_ARCHETYPE_RESERVED_TOML_KEYS:
            continue
        flat_attrs[str(key)] = d.pop(key)
    merged = {**explicit_attrs, **flat_attrs}
    out = dict(d)
    if merged:
        out["attributes"] = merged
    return out


def _parse_unit_archetype_index(raw: object) -> dict[str, UnitArchetypeRow]:
    if raw is None or raw == []:
        return {}
    if not isinstance(raw, list):
        raise TypeError(f"unit_archetypes must be a list, got {type(raw).__name__}")
    out: dict[str, UnitArchetypeRow] = {}
    for i, item in enumerate(raw):
        d = ensure_dict_table(item, f"unit_archetypes[{i}]")
        row = parse_scenario_row(
            UnitArchetypeRow,
            _normalize_unit_archetype_row_mapping(d),
            path=f"unit_archetypes[{i}]",
        )
        if row.name in out:
            raise ValueError(f"duplicate unit_archetypes name {row.name!r}")
        out[row.name] = row
    return out


def _load_unit_archetypes(data: dict[str, Any]) -> dict[str, UnitArchetypeRow]:
    """Merge ``[[unit_archetypes]]`` / ``[[unit_archetype]]`` into a name → row index."""
    rows: list[Any] = []
    _u_arch = data.get("unit_archetypes")
    _u_arch1 = data.get("unit_archetype")
    if isinstance(_u_arch, list):
        rows.extend(_u_arch)
    if isinstance(_u_arch1, list):
        rows.extend(_u_arch1)
    return _parse_unit_archetype_index(rows if rows else None)


def _load_scenario_units(
    data: dict[str, Any],
    archetype_by_name: dict[str, UnitArchetypeRow],
) -> list[UnitRow]:
    """Parse ``[[units]]`` and ``[[unit_placements]]`` into a flat unit list."""
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
            squad_graphics = _optional_nonempty_str(g, "graphics")
            graphics = squad_graphics if squad_graphics is not None else ar.graphics
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
            graphics = _optional_nonempty_str(g, "graphics")
        if "positions" not in g:
            raise ValueError(
                f"unit_placements[{si}] requires key 'positions' (list of placement tables)"
            )
        pos_rows = parse_positions_list(
            g["positions"], f"unit_placements[{si}].positions"
        )
        base: dict[str, Any] = {
            "type": unit_type,
            "faction": faction,
            "health": squad_health,
            "active": squad_active,
        }
        if graphics is not None:
            base["graphics"] = graphics
        archetype_attr_defaults: dict[str, Any] = dict(ar.attributes) if arch else {}
        squad_level_attrs = coerce_unit_attributes(g.get("attributes"))
        for pi, m in enumerate(pos_rows):
            row = dict(m)
            merged_attrs = {**archetype_attr_defaults, **squad_level_attrs}
            pos_attrs = row.get("attributes")
            if isinstance(pos_attrs, dict):
                merged_attrs = {**merged_attrs, **pos_attrs}
            if merged_attrs:
                row["attributes"] = merged_attrs
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

    return units
