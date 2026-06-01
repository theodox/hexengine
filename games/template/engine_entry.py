"""Manifest entry callable (see hexengine_pack.toml)."""

from __future__ import annotations

from hexengine.gamedef.protocol import GameDefinition

from .registry import build_game_definition


def load_game_definition() -> GameDefinition:
    return build_game_definition()


__all__ = ["load_game_definition"]
