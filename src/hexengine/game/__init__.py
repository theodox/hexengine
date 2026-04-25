"""
Game package for hexengine.

This package contains the main game logic and state management.
Requires Pyodide/browser (`js`, DOM); importing this package outside the
browser will fail with a normal ImportError — do not import `Game` from
server-only code.
"""

from __future__ import annotations

from .game import Game

__all__ = ["Game"]
