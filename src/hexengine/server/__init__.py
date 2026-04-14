"""
Server module for multiplayer game coordination.

The server is the single source of truth, managing game state via ActionManager.
Clients send action requests, server validates and executes them, then broadcasts
state updates to all connected clients.
"""

from __future__ import annotations

from .game_server import GameServer
from .protocol import (
    ActionRequest,
    Message,
    StateUpdate,
)

__all__ = [
    "GameServer",
    "Message",
    "ActionRequest",
    "StateUpdate",
]
