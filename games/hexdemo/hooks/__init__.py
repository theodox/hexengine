"""
Hexdemo hook implementations.

**`TitleHooks`** (in-match rules) — movement, attack, UI, overlays; assembled in
`build_hooks()` and exposed on `HexdemoGameDefinition.hooks`.

**Manifest title-load** — splash/setup/server log in `hexdemo.hooks.title_load`;
wired from `hexengine_pack.toml` `[hooks.title_load]`, not via `TitleHooks`.

**Phase transition** — `HexdemoGameDefinition.after_phase_transition` clears
phase-scoped combat state via `combat_transitions`.

Engine catalog defaults (`hexengine.hooks.internal`) complement `TitleHooks` when
hooks return `ENGINE_DEFAULT` or omit a field.
"""

from __future__ import annotations

from hexengine.hooks.title import TitleHooks
from hexengine.hooks.wiring import assemble_title_hooks

from . import (
    arcs,
    attack,
    markers,
    movement,
    overlays,
    segment_presentation,
    segment_ui_registry,
    turn_action_dock,
    ui,
)


def build_hooks() -> TitleHooks:
    return assemble_title_hooks(
        movement,
        attack,
        ui,
        overlays,
        turn_action_dock,
        segment_presentation,
        segment_ui_registry,
        markers,
        arcs,
    )


__all__ = ["build_hooks"]
