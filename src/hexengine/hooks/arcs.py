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
from ..arcs.registry import TurnArcRegistry
from .core import ENGINE_DEFAULT


@dataclass(frozen=True, slots=True)
class ArcsHooks:
    """Declared-arc providers consulted by the authoritative server."""

    combat_arc: Callable[[], ArcSpec] | None = None
    combat_rules_binding: Callable[[], object] | None = None
    movement_arc: Callable[[], ArcSpec] | None = None
    turn_arc_registry: Callable[[], TurnArcRegistry] | None = None

    def combat_arc_spec(self) -> ArcSpec | object:
        """The title's combat arc bundle, or ENGINE_DEFAULT when not provided."""

        if self.combat_arc is None:
            return ENGINE_DEFAULT
        return self.combat_arc()

    def combat_rules_binding_spec(self) -> object:
        """Optional unified combat binding for contract validation."""

        if self.combat_rules_binding is None:
            return ENGINE_DEFAULT
        return self.combat_rules_binding()

    def movement_arc_spec(self) -> ArcSpec | object:
        """The title's movement arc bundle, ``ENGINE_MOVEMENT_ARC_PRESET``, or ``ENGINE_DEFAULT``."""

        if self.movement_arc is None:
            return ENGINE_DEFAULT
        return self.movement_arc()

    def turn_arc_registry_spec(self) -> TurnArcRegistry | object:
        """The title's turn schedule + routine arc registry, or ENGINE_DEFAULT."""

        if self.turn_arc_registry is None:
            return ENGINE_DEFAULT
        return self.turn_arc_registry()


class ArcHook(StrEnum):
    """Stable slot ids for `bind_title_hook` (values match `ArcsHooks` field names)."""

    COMBAT_ARC = "combat_arc"
    COMBAT_RULES_BINDING = "combat_rules_binding"
    MOVEMENT_ARC = "movement_arc"
    TURN_ARC_REGISTRY = "turn_arc_registry"


ArcHook._hexengine_hook_bundle = "arcs"


__all__ = ["ArcHook", "ArcsHooks"]
