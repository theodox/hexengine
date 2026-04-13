"""
Hexdemo — reference game pack (scenarios, resources, Python title code).

Import with `games` on `PYTHONPATH` (`import hexdemo`), or rely on the engine
to prepend `…/games` when loading a hexdemo scenario from the repo layout.
"""

from __future__ import annotations

__version__ = "0.1.0"

from . import boot, constants, game_config, registry

__all__ = ["__version__", "boot", "constants", "game_config", "registry"]
