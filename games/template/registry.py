"""Entry points for hexengine.game_packs.registry."""

from __future__ import annotations

from hexengine.gamedef.protocol import GameDefinition

from .game_config import default_match_config, game_definition_from_config


def build_game_definition() -> GameDefinition:
    return game_definition_from_config(default_match_config())


__all__ = ["build_game_definition"]
