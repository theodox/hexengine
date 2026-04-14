"""Client -> server protocol payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .internals import client_message


@client_message("undo_request")
@dataclass
class UndoRequest:
    """Request from client to undo the last action."""

    player_id: str


@client_message("redo_request")
@dataclass
class RedoRequest:
    """Request from client to redo the next action."""

    player_id: str


@client_message("action_request")
@dataclass
class ActionRequest:
    """Request from client to execute an action."""

    action_type: str  # "MoveUnit", "DeleteUnit", etc.
    params: dict[str, Any]  # Action parameters
    player_id: str


@client_message("load_snapshot")
@dataclass
class LoadSnapshotRequest:
    """Request to replace game state from a wire-format snapshot (server-authoritative)."""

    game_state: dict[str, Any]
    player_id: str = ""


@client_message("join_game")
@dataclass
class JoinGameRequest:
    """Request to join a game."""

    player_name: str
    faction: str | None = None  # Preferred faction, or None for auto-assign


@client_message("leave_game")
@dataclass
class LeaveGameRequest:
    """Client request to leave the game session."""

