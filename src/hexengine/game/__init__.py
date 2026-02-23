"""
Game package for hexengine.

This package contains the main game logic and state management.
Game/NetworkGame require Pyodide (browser); on the server they are None.
"""

try:
    from .game import Game
    from .network_game import NetworkGame
except ImportError:
    # No Pyodide (e.g. server): avoid pulling in document/js
    Game = None  # type: ignore[misc, assignment]
    NetworkGame = None  # type: ignore[misc, assignment]

__all__ = ["Game", "NetworkGame"]
