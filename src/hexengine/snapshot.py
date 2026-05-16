"""
Snapshot-shaped payloads for `GameState` (extension buckets, `rng_log`, …).

Title hooks build **Python** values; the engine normalizes them to JSON-safe trees
before they are stored or broadcast. Naming here is **snapshot**, not wire: the
same structures are what `hexengine.state.snapshot.game_state_to_wire_dict`
serializes for persistence and client sync.

Titles may nest `@dataclass` instances whose fields are themselves snapshot-safe
(primitives, dict/list/tuple of snapshot-safe values, or nested dataclasses). The
engine expands dataclasses with `dataclasses.asdict` and rejects values that are
not JSON-serializable (including non-finite floats).
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any


def normalize_snapshot_value(obj: Any) -> Any:
    """
    Recursively convert dataclass instances to plain dict/list trees.

    Mappings become `dict[str, Any]` with stringified keys. Tuples normalize
    element-wise and stay tuples. Lists stay lists.

    Raises:
        TypeError: If a value cannot be coerced into a snapshot-safe tree.
        ValueError: If a float is non-finite (not JSON-safe with `allow_nan=False`).
    """
    if obj is None or isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, str)):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError(
                f"Non-finite float not allowed in snapshot payloads: {obj!r}"
            )
        return obj
    if isinstance(obj, Enum):
        return normalize_snapshot_value(obj.value)
    if is_dataclass(obj) and not isinstance(obj, type):
        return normalize_snapshot_value(asdict(obj))
    if isinstance(obj, dict):
        return {str(k): normalize_snapshot_value(v) for k, v in obj.items()}
    if isinstance(obj, Mapping) and not isinstance(obj, (str, bytes, bytearray)):
        return {str(k): normalize_snapshot_value(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize_snapshot_value(x) for x in obj]
    if isinstance(obj, tuple):
        return tuple(normalize_snapshot_value(x) for x in obj)
    raise TypeError(
        f"Unsupported type in snapshot payload: {type(obj).__name__!r} "
        "(use primitives, dict/list/tuple, Enum, or dataclass of snapshot-safe fields)"
    )


def normalize_snapshot_mapping(m: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a mapping into a string-keyed dict of snapshot-safe values."""
    if not isinstance(m, Mapping):
        raise TypeError("normalize_snapshot_mapping expects a mapping root")
    out = normalize_snapshot_value(dict(m))
    if not isinstance(out, dict):
        raise TypeError("normalize_snapshot_mapping expects a mapping root")
    return out


def assert_snapshot_json_serializable(obj: Any, *, context: str = "") -> None:
    """
    Fail fast if `obj` is not encodable as strict JSON.

    Args:
        obj: Already-normalized tree (e.g. output of `normalize_snapshot_mapping`).
        context: Optional suffix for the error message (e.g. `\" (Attack.rng_entry)\"`).
    """
    try:
        json.dumps(obj, allow_nan=False)
    except (TypeError, ValueError) as e:
        raise TypeError(
            f"Snapshot payload is not JSON-serializable{context}: {e}"
        ) from e


def attack_resolution_snapshot_fields(
    *, rng_entry: Any | None, effects: Any | None
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """
    Normalize `AttackResolution.rng_entry` and `AttackResolution.effects`.

    Each field may be `None`, a mapping, or a dataclass instance that normalizes to
    a dict (nested dataclasses are expanded). `ENGINE_DEFAULT` is treated like
    `None` so duck-typed hook returns do not trip serialization.

    Returns:
        `(rng_dict | None, effects_dict | None)` ready for `Attack` and
        `ApplyCombatEffects`.

    Raises:
        TypeError: If a non-`None` field does not normalize to a dict or is not
            JSON-serializable.
    """
    from hexengine.hooks.core import ENGINE_DEFAULT

    if rng_entry is None or rng_entry is ENGINE_DEFAULT:
        n_rng: dict[str, Any] | None = None
    else:
        n = normalize_snapshot_value(rng_entry)
        if not isinstance(n, dict):
            raise TypeError(
                "AttackResolution.rng_entry must be a mapping or a dataclass "
                "that normalizes to a dict"
            )
        assert_snapshot_json_serializable(n, context=" (Attack.rng_entry)")
        n_rng = n
    if effects is None or effects is ENGINE_DEFAULT:
        n_eff: dict[str, Any] | None = None
    else:
        n = normalize_snapshot_value(effects)
        if not isinstance(n, dict):
            raise TypeError(
                "AttackResolution.effects must be a mapping or a dataclass "
                "that normalizes to a dict"
            )
        assert_snapshot_json_serializable(n, context=" (AttackResolution.effects)")
        n_eff = n
    return n_rng, n_eff


__all__ = [
    "assert_snapshot_json_serializable",
    "attack_resolution_snapshot_fields",
    "normalize_snapshot_mapping",
    "normalize_snapshot_value",
]
