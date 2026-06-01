"""
Single runtime gateway to hexengine.authoring (strict import boundary).

Only this module and hooks.internal.contracts may import hexengine.authoring
from engine runtime code. Titles import authoring directly.
"""

from __future__ import annotations

from typing import Any, Protocol

from ...arcs import ArcSpec
from ...arcs.movement_arc_decl import resolve_moving_faction
from ...authoring.patterns.movement import build_movement_arc
from ...authoring.validate import validate_arc_contract_for_definition


class MovementArcHost(Protocol):
    """Minimal GameServer surface for host-bound movement arc effects."""

    def movement_arc_effects_binding(self) -> Any: ...


def validate_declared_arcs(game_definition: Any) -> list[str]:
    """Run arc/registry validation for a game definition (startup)."""

    return validate_arc_contract_for_definition(game_definition)


def build_default_movement_arc_spec(host: MovementArcHost) -> ArcSpec:
    """Assemble the engine default stepwise movement arc for this server host."""

    effects = host.movement_arc_effects_binding()
    return ArcSpec(
        arc=build_movement_arc(effects),
        owner_resolver=resolve_moving_faction,
    )


__all__ = [
    "MovementArcHost",
    "build_default_movement_arc_spec",
    "validate_declared_arcs",
]
