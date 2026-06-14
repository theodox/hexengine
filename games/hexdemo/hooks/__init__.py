"""
Hexdemo hook implementations.

**`TitleHooks`** (in-match rules) — modification, interaction, UI, overlays; assembled in
`build_hooks()` and exposed on `HexdemoGameDefinition.hooks`.
"""

from __future__ import annotations

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


def build_hooks() -> TitleHooks:
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
    )


__all__ = ["build_hooks"]
