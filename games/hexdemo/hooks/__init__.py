"""
Hexdemo hook implementations.

**`TitleHooks`** (in-match rules) — movement, attack, UI, overlays; assembled in
`build_hooks()` and exposed on `HexdemoGameDefinition.hooks`.

**Manifest title-load** — splash/setup/server log in `hexdemo.hooks.title_load`;
wired from `hexengine_pack.toml` `[hooks.title_load]`, not via `TitleHooks`.

**Turn schedule** — `hexdemo.hooks.turn_schedule` (e.g. `before_union_move`) from
`HexdemoGameDefinition.after_phase_transition`.

Engine catalog defaults (`hexengine.hooks.internal`) complement `TitleHooks` when
hooks return `ENGINE_DEFAULT` or omit a field.
"""

from __future__ import annotations

from hexengine.hooks.title import TitleHooks
from hexengine.hooks.wiring import assemble_title_hooks

from . import arcs, attack, markers, movement, overlays, turn_action_dock, ui


def build_hooks() -> TitleHooks:
    return assemble_title_hooks(
        movement,
        attack,
        ui,
        overlays,
        turn_action_dock,
        markers,
        arcs,
    )


__all__ = ["build_hooks"]
