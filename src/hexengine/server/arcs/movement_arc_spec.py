"""
Host-bound stepwise movement ``ArcSpec`` assembly (engine preset, not title patterns).
"""

from __future__ import annotations

from typing import Any, Protocol

from ...arcs import ArcSpec
from ...arcs.movement_arc_build import build_movement_arc
from ...arcs.movement_arc_decl import OWNER_MOVING, resolve_moving_faction
from ...authoring.patterns.combat import OWNER_RETREATING
from ...hooks.core import ENGINE_DEFAULT
from ...state import GameState
from .movement_arc_effects import MovementArcEffects


class MovementArcHost(Protocol):
    """Minimal server surface for host-bound movement arc effects."""

    hooks: Any


def resolve_retreat_open_owner(host: MovementArcHost, state: GameState) -> str | None:
    """Faction with a pending retreat obligation (first active unit found)."""

    for uid, unit in state.board.units.items():
        if not unit.active:
            continue
        rem_raw = host.hooks.modification.retreat_remaining(state, uid)
        if rem_raw is ENGINE_DEFAULT or rem_raw is None:
            continue
        try:
            if int(rem_raw) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        faction = str(unit.faction).strip()
        if faction:
            return faction
    return None


def resolve_movement_arc_owner(
    host: MovementArcHost, key: str, state: GameState
) -> str | None:
    if key == OWNER_MOVING:
        return resolve_moving_faction(key, state)
    if key == OWNER_RETREATING:
        return resolve_retreat_open_owner(host, state)
    return None


def build_host_bound_movement_arc_spec(host: MovementArcHost) -> ArcSpec:
    """Assemble the engine stepwise movement arc for an authoritative server host."""

    effects = MovementArcEffects(host)  # type: ignore[arg-type]

    def owner_resolver(key: str, state: GameState) -> str | None:
        return resolve_movement_arc_owner(host, key, state)

    return ArcSpec(
        arc=build_movement_arc(effects),
        owner_resolver=owner_resolver,
    )


__all__ = [
    "MovementArcHost",
    "build_host_bound_movement_arc_spec",
    "resolve_movement_arc_owner",
    "resolve_retreat_open_owner",
]
