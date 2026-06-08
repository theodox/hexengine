"""Unit ``attributes`` patch DTO (title-defined JSON-safe unit metadata)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class UnitAttributesPatch:
    """Partial update to ``UnitState.attributes`` (shallow merge)."""

    values: dict[str, Any] = field(default_factory=dict)
    remove_keys: tuple[str, ...] = ()

    def to_action(self, unit_id: str) -> "ApplyUnitAttributesPatch":
        from .actions import ApplyUnitAttributesPatch

        return ApplyUnitAttributesPatch(unit_id, self)


__all__ = ["UnitAttributesPatch"]
