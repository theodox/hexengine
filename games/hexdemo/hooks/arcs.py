"""
Hexdemo arc providers (composable arcs, Phase 2b).

Exposes the declared combat-cleanup arc (see `hexdemo.combat_arc`) on the engine's
`arcs` hook bundle so the generic runner can drive it. The arc is pure data, so it is
built once at import.
"""

from __future__ import annotations

from hexengine.arcs import ArcSpec
from hexengine.hooks.arcs import ArcHook
from hexengine.hooks.wiring import bind_title_hook

from ..combat_arc import build_combat_arc, resolve_owner_ref

_COMBAT_ARC_SPEC = ArcSpec(arc=build_combat_arc(), owner_resolver=resolve_owner_ref)


@bind_title_hook(ArcHook.COMBAT_ARC)
def combat_arc() -> ArcSpec:
    return _COMBAT_ARC_SPEC


__all__ = ["combat_arc"]
