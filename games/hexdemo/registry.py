"""
Named entry points for `hexengine.gamedef.protocol.GameDefinition` factories.

The engine loads this pack via hexengine_pack.toml and hexdemo.engine_entry.
Match rules (turn order, factions, …) are assembled in hexdemo.game_config — edit
HexdemoMatchConfig there (or build your own and extend this module) rather than only
swapping ids here.
"""

from __future__ import annotations

from hexengine.gamedef.protocol import GameDefinition

from .game_config import default_match_config, game_definition_from_config


def build_game_definition() -> GameDefinition:
    """Return a new `GameDefinition` for this pack's static schedule."""
    return game_definition_from_config(default_match_config())
