"""
Named entry points for `hexengine.gamedef.protocol.GameDefinition` factories.

The engine loads this pack via hexengine_pack.toml (`hexdemo.registry.build_game_definition`).
Turn rota is declared in `arcs/turn_schedule.py` and wired via `hooks.build_hooks`.
Match settings (factions, movement budget) live in `game_config.HexdemoMatchConfig`.
"""

from __future__ import annotations

from hexengine.gamedef.protocol import GameDefinition

from .game_config import default_match_config, game_definition_from_config


def build_game_definition() -> GameDefinition:
    """Return a new `GameDefinition` for this pack (registry-backed turn rota)."""
    return game_definition_from_config(default_match_config())
