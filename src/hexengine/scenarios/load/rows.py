"""
Build scenario row dataclasses from TOML dicts using `dataclasses.field` metadata.

Schema rows use `hexengine.scenarios.schema.toml_field` and optional
`hexengine.scenarios.schema.scenario_toml_table` on the dataclass.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import MISSING, fields
from typing import Any, TypeVar, get_type_hints

from .coercion import coerce_movement_cost, parse_position

T = TypeVar("T")


def coerce_unit_attributes(raw: object) -> dict[str, Any]:
    """
    Parse ``[[units]]`` / placement ``attributes`` as a shallow string-keyed map.

    Accepts ``null`` / missing coercer path as ``{}`` via caller; TOML tables only here.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise TypeError(
            f"attributes must be a TOML table, got {type(raw).__name__}"
        )
    return {str(k): v for k, v in raw.items()}


def ensure_dict_table(value: object, path: str) -> dict[str, Any]:
    """Require a TOML inline table / section as `dict`."""
    if not isinstance(value, dict):
        raise TypeError(f"{path} must be a table, got {type(value).__name__}")
    return value


def parse_positions_list(raw: object, path: str) -> list[dict[str, Any]]:
    """
    Parse `positions` (TOML): a list of either `[col, row]` (odd-q) or inline tables.

    A length-2 array is normalized to a dict with key `position` (odd-q `[col, row]`)
    so plain coordinate rows need not repeat that key.
    """
    if not isinstance(raw, list):
        raise TypeError(f"{path} must be a list, got {type(raw).__name__}")
    out: list[dict[str, Any]] = []
    for mi, item in enumerate(raw):
        p = f"{path}[{mi}]"
        if isinstance(item, dict):
            out.append(ensure_dict_table(item, p))
            continue
        if isinstance(item, list | tuple):
            if len(item) != 2:
                raise ValueError(
                    f"{p}: expected [col, row] with two integers, got {item!r}"
                )
            try:
                col, row = int(item[0]), int(item[1])
            except (TypeError, ValueError) as e:
                raise ValueError(
                    f"{p}: [col, row] entries must be integers, got {item!r}"
                ) from e
            out.append({"position": [col, row]})
            continue
        raise TypeError(
            f"{p}: expected inline table or [col, row], got {type(item).__name__}"
        )
    return out


_COERCERS: dict[str, Any] = {
    "position": parse_position,
    "movement_cost": coerce_movement_cost,
    "unit_attributes": coerce_unit_attributes,
}


def parse_scenario_row(
    cls: type[T],
    row: Mapping[str, Any],
    *,
    path: str,
    base: Mapping[str, Any] | None = None,
) -> T:
    """
    Instantiate a dataclass row from TOML keys declared via `field(metadata=toml_field(...))`.

    `base` is merged under `row` (row wins) so unit_placement / group defaults can be applied
    using the same TOML key names as in the file (e.g. `positions` rows under `[[terrain_groups]]`).
    """
    merged: dict[str, Any] = {**(base or {}), **dict(row)}
    hints = get_type_hints(cls)
    kwargs: dict[str, Any] = {}

    for f in fields(cls):
        meta: Mapping[str, Any] = f.metadata or {}
        tk = str(meta.get("toml_key", f.name))
        optional_str = bool(meta.get("optional_str"))
        nonempty = bool(meta.get("nonempty"))

        if tk not in merged:
            if f.default is not MISSING:
                kwargs[f.name] = f.default
            elif f.default_factory is not MISSING:
                kwargs[f.name] = f.default_factory()
            else:
                raise ValueError(f"{path} missing required key {tk!r}")
            continue

        raw_val = merged[tk]

        if optional_str:
            if raw_val is None:
                kwargs[f.name] = None
            else:
                s = str(raw_val).strip()
                kwargs[f.name] = s if s else None
            continue

        if nonempty:
            if raw_val is None:
                raise ValueError(f"{path} requires non-empty {tk!r}")
            s = str(raw_val).strip()
            if not s:
                raise ValueError(f"{path} requires non-empty {tk!r}")
            kwargs[f.name] = s
            continue

        coerce_name = meta.get("coerce")
        if isinstance(coerce_name, str) and coerce_name in _COERCERS:
            kwargs[f.name] = _COERCERS[coerce_name](raw_val)
            continue

        ann = hints.get(f.name, type(raw_val))
        if ann is bool:
            kwargs[f.name] = bool(raw_val)
        elif ann is int:
            kwargs[f.name] = int(raw_val)
        elif ann is float:
            kwargs[f.name] = float(raw_val)
        elif ann is str:
            kwargs[f.name] = str(raw_val)
        else:
            kwargs[f.name] = raw_val

    return cls(**kwargs)
