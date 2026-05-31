"""
Title hook bundle for declared turn arcs.

A title exposes its declared arcs here so the engine's generic runner can drive them
without knowing any title shapes. Phase 2 has a single slot, the combat arc; Phase 4
grows this into the full turn-arc registry/schedule.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from ..arcs import ArcSpec
from .core import ENGINE_DEFAULT


@dataclass(frozen=True, slots=True)
class ArcsHooks:
    """Declared-arc providers consulted by the authoritative server."""

    combat_arc: Callable[[], ArcSpec] | None = None
    movement_arc: Callable[[], ArcSpec] | None = None

    def combat_arc_spec(self) -> ArcSpec | object:
        """The title's combat arc bundle, or ENGINE_DEFAULT when not provided."""

        if self.combat_arc is None:
            return ENGINE_DEFAULT
        return self.combat_arc()

    def movement_arc_spec(self) -> ArcSpec | object:
        """The title's movement arc bundle, or ENGINE_DEFAULT when not provided."""

        if self.movement_arc is None:
            return ENGINE_DEFAULT
        return self.movement_arc()


class ArcHook(StrEnum):
    """Stable slot ids for `bind_title_hook` (values match `ArcsHooks` field names)."""

    COMBAT_ARC = "combat_arc"
    MOVEMENT_ARC = "movement_arc"


ArcHook._hexengine_hook_bundle = "arcs"


__all__ = ["ArcHook", "ArcsHooks"]
