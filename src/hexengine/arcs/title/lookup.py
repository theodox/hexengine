"""
Resolve declared arc specs from TitleHooks (title allowlist; no server import).

GameServer and segment projection use the same lookup rules: routine arcs from the
turn registry, overlay arc from ArcHook.COMBAT_ARC, optional movement arc when the
title binds ArcHook.MOVEMENT_ARC to ArcSpec or ENGINE_MOVEMENT_ARC_PRESET.
"""

from __future__ import annotations

from typing import Any, Protocol

from ...hooks.core import ENGINE_MOVEMENT_ARC_PRESET
from ...hooks.title import TitleHooks
from ..registry import TurnArcRegistry
from ..runner import ArcSpec


class ArcLookupHost(Protocol):
    """Minimal host for arc id resolution (GameServer or title segment helpers)."""

    hooks: TitleHooks

    def movement_arc_spec(self) -> ArcSpec | None: ...


def turn_arc_registry_from_hooks(hooks: TitleHooks) -> TurnArcRegistry | None:
    """The title's turn arc registry, or None when not declared."""

    raw = hooks.arcs.turn_arc_registry_spec()
    return raw if isinstance(raw, TurnArcRegistry) else None


def combat_arc_spec(hooks: TitleHooks) -> ArcSpec | None:
    """The title's declared overlay (interaction) arc bundle, or None."""

    raw = hooks.arcs.combat_arc_spec()
    return raw if isinstance(raw, ArcSpec) else None


def movement_arc_spec_for_host(host: Any) -> ArcSpec | None:
    """Movement arc bundle from hooks.

    Titles return a custom ``ArcSpec``, or ``ENGINE_MOVEMENT_ARC_PRESET`` to use the
    host's built-in preset (``GameServer.movement_arc_spec``). When the hook is
    unbound (``ENGINE_DEFAULT``), there is no movement arc.
    """

    hooks = host.hooks
    raw = hooks.arcs.movement_arc_spec()
    if isinstance(raw, ArcSpec):
        return raw
    if raw is ENGINE_MOVEMENT_ARC_PRESET:
        fn = getattr(host, "movement_arc_spec", None)
        if callable(fn):
            return fn()
    return None


def lookup_arc_spec(host: Any, arc_id: str) -> ArcSpec | None:
    """Resolve any declared arc by id (routine, overlay, movement)."""

    hooks = host.hooks
    reg = turn_arc_registry_from_hooks(hooks)
    if reg is not None:
        spec = reg.routine_specs.get(str(arc_id))
        if spec is not None:
            return spec

    combat = combat_arc_spec(hooks)
    if combat is not None and combat.arc.id == arc_id:
        return combat

    movement = movement_arc_spec_for_host(host)
    if movement is not None and movement.arc.id == arc_id:
        return movement

    return None


def attach_arc_lookup(host: Any) -> Any:
    """Attach lookup_arc_spec(arc_id) to a host that already has hooks."""

    host.lookup_arc_spec = lambda arc_id: lookup_arc_spec(host, arc_id)
    return host


__all__ = [
    "ArcLookupHost",
    "attach_arc_lookup",
    "combat_arc_spec",
    "lookup_arc_spec",
    "movement_arc_spec_for_host",
    "turn_arc_registry_from_hooks",
]
