"""
Server module for multiplayer game coordination.

The server is the single source of truth, managing game state via ActionManager.
Clients send action requests, server validates and executes them, then broadcasts
state updates to all connected clients.
"""

from .game_server import GameServer
from .protocol import Message, MessageType, ActionRequest, StateUpdate

__all__ = [
    "GameServer",
    "Message",
    "MessageType", 
    "ActionRequest",
    "StateUpdate",
]
