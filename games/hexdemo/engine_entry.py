"""
Stable entry point for hexengine.game_packs.registry (manifest-driven load).

Returns the title's single static turn schedule (see hexdemo.game_config).
"""

from __future__ import annotations

from hexengine.gamedef.protocol import GameDefinition

from .registry import build_game_definition


def load_game_definition() -> GameDefinition:
    return build_game_definition()
