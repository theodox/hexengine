"""
Named entry points for `hexengine.gamedef.protocol.GameDefinition` factories.

The engine calls `build_game_definition` when a scenario lives under
`hexdemo/scenarios/`. Match rules (turn order, factions, …) are assembled in
`hexdemo.game_config` — edit `hexdemo.game_config.HexdemoMatchConfig`
there (or build your own and extend this module) rather than only swapping ids here.
"""

from __future__ import annotations

from hexengine.gamedef.protocol import GameDefinition

from .game_config import HexdemoMatchConfig, game_definition_from_config

_REGISTRY_KEYS: tuple[str, ...] = ("default", "interleaved", "sequential")


def build_game_definition(name: str = "default") -> GameDefinition:
    """
    Return a new `GameDefinition` instance for the given schedule id.

    Raises:
        KeyError: if `name` is not registered.
    """
    key = name.strip().lower()
    if key not in _REGISTRY_KEYS:
        raise KeyError(f"Unknown hexdemo game definition id: {key!r}")
    return game_definition_from_config(HexdemoMatchConfig.from_registry_key(key))


def registered_game_definition_ids() -> tuple[str, ...]:
    """Stable ids (including aliases) understood by `build_game_definition`."""
    return tuple(sorted(set(_REGISTRY_KEYS)))
