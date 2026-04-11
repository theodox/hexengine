"""
Build scenario row dataclasses from TOML dicts using :func:`dataclasses.field` metadata.

Schema rows use :func:`~hexengine.scenarios.schema.toml_field` and optional
:func:`~hexengine.scenarios.schema.scenario_toml_table` on the dataclass.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import MISSING, fields
from typing import Any, TypeVar, get_type_hints

from .coercion import coerce_movement_cost, parse_position

T = TypeVar("T")


def ensure_dict_table(value: object, path: str) -> dict[str, Any]:
    """Require a TOML inline table / section as ``dict``."""
    if not isinstance(value, dict):
        raise TypeError(f"{path} must be a table, got {type(value).__name__}")
    return value


def parse_members_list(raw: object, path: str) -> list[dict[str, Any]]:
    """Require ``members`` to be a list of tables."""
    if not isinstance(raw, list):
        raise TypeError(f"{path} must be a list, got {type(raw).__name__}")
    out: list[dict[str, Any]] = []
    for mi, item in enumerate(raw):
        p = f"{path}[{mi}]"
        out.append(ensure_dict_table(item, p))
    return out


_COERCERS: dict[str, Any] = {
    "position": parse_position,
    "movement_cost": coerce_movement_cost,
}


def parse_scenario_row(
    cls: type[T],
    row: Mapping[str, Any],
    *,
    path: str,
    base: Mapping[str, Any] | None = None,
) -> T:
    """
    Instantiate a dataclass row from TOML keys declared via ``field(metadata=toml_field(...))``.

    ``base`` is merged under ``row`` (row wins) so unit_placement / group defaults can be applied
    using the same TOML key names as in the file.
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
