"""
Game package for hexengine.

This package contains the main game logic and state management.
Requires Pyodide/browser (``js``, DOM); importing this package outside the
browser will fail with a normal ImportError — do not import ``Game`` or
``NetworkGame`` from server-only code.
"""

from __future__ import annotations

from .game import Game
from .network_game import NetworkGame

__all__ = ["Game", "NetworkGame"]
