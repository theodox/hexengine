"""
Hexdemo hook implementations.

**`TitleHooks`** (in-match rules) — modification, interaction, UI, overlays; assembled in
`build_hooks()` and exposed on `HexdemoGameDefinition.hooks`.
"""

from __future__ import annotations

from hexengine.arcs.registry import TurnArcRegistry
from hexengine.hooks.title import TitleHooks
from hexengine.hooks.wiring import assemble_title_hooks

from ..arcs import wiring as arc_wiring
from . import (
    interaction,
    markers,
    modification,
    overlays,
    segment_presentation,
    segment_ui_registry,
    turn_action_dock,
    ui,
)


def build_hooks(turn_registry: TurnArcRegistry | None = None) -> TitleHooks:
    if turn_registry is None:
        from ..arcs.turn_schedule import build_hexdemo_turn_arc_registry

        turn_registry = build_hexdemo_turn_arc_registry()
    arcs_override = {"turn_arc_registry": lambda: turn_registry}
    return assemble_title_hooks(
        modification,
        interaction,
        arc_wiring,
        ui,
        overlays,
        turn_action_dock,
        segment_presentation,
        segment_ui_registry,
        markers,
        arcs=arcs_override,
    )


__all__ = ["build_hooks"]
