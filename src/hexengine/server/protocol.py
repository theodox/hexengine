"""
Client-server communication protocol.

Defines message types and data structures for communication between
clients and server.
"""

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Optional
import json


class MessageType(Enum):
    """Types of messages in the protocol."""

    # Client -> Server
    ACTION_REQUEST = "action_request"
    JOIN_GAME = "join_game"
    LEAVE_GAME = "leave_game"
    UNDO_REQUEST = "undo_request"
    REDO_REQUEST = "redo_request"

    # Server -> Client
    STATE_UPDATE = "state_update"
    ACTION_RESULT = "action_result"
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    ERROR = "error"


@dataclass
class Message:
    """Base message structure."""

    type: MessageType
    payload: dict[str, Any]

    def to_json(self) -> str:
        """Serialize message to JSON."""
        return json.dumps({"type": self.type.value, "payload": self.payload})

    @classmethod
    def from_json(cls, data: str) -> "Message":
        """Deserialize message from JSON."""
        obj = json.loads(data)
        return cls(type=MessageType(obj["type"]), payload=obj["payload"])


@dataclass
class UndoRequest:
    """Request from client to undo the last action."""

    player_id: str

    @classmethod
    def from_message(cls, message: Message) -> "UndoRequest":
        """Create from message."""
        return cls(player_id=message.payload["player_id"])

    def to_message(self) -> Message:
        """Convert to message."""
        return Message(
            type=MessageType.UNDO_REQUEST, payload={"player_id": self.player_id}
        )


@dataclass
class RedoRequest:
    """Request from client to redo the next action."""

    player_id: str

    @classmethod
    def from_message(cls, message: Message) -> "RedoRequest":
        """Create from message."""
        return cls(player_id=message.payload["player_id"])

    def to_message(self) -> Message:
        """Convert to message."""
        return Message(
            type=MessageType.REDO_REQUEST, payload={"player_id": self.player_id}
        )


@dataclass
class ActionRequest:
    """Request from client to execute an action."""

    action_type: str  # "MoveUnit", "DeleteUnit", etc.
    params: dict[str, Any]  # Action parameters
    player_id: str

    def to_message(self) -> Message:
        """Convert to Message."""
        return Message(
            type=MessageType.ACTION_REQUEST,
            payload={
                "action_type": self.action_type,
                "params": self.params,
                "player_id": self.player_id,
            },
        )

    @classmethod
    def from_message(cls, msg: Message) -> "ActionRequest":
        """Create from Message."""
        return cls(**msg.payload)


@dataclass
class StateUpdate:
    """Full or partial state update from server."""

    game_state: dict[str, Any]  # Serialized GameState
    sequence_number: int  # For ordering/detecting missed updates
    map_display: Optional[dict[str, Any]] = None  # From scenario MapDisplayConfig
    global_styles: Optional[dict[str, Any]] = None  # GlobalStylesConfig.to_wire_dict()
    unit_graphics: Optional[dict[str, Any]] = None  # unit type -> template wire dict
    server_package_version: Optional[str] = None  # hexes wheel version on server

    def to_message(self) -> Message:
        """Convert to Message."""
        payload: dict[str, Any] = {
            "game_state": self.game_state,
            "sequence_number": self.sequence_number,
        }
        if self.map_display is not None:
            payload["map_display"] = self.map_display
        if self.global_styles is not None:
            payload["global_styles"] = self.global_styles
        if self.unit_graphics is not None:
            payload["unit_graphics"] = self.unit_graphics
        if self.server_package_version is not None:
            payload["server_package_version"] = self.server_package_version
        return Message(type=MessageType.STATE_UPDATE, payload=payload)

    @classmethod
    def from_message(cls, msg: Message) -> "StateUpdate":
        """Create from Message."""
        p = msg.payload
        return cls(
            game_state=p["game_state"],
            sequence_number=p["sequence_number"],
            map_display=p.get("map_display"),
            global_styles=p.get("global_styles"),
            unit_graphics=p.get("unit_graphics"),
            server_package_version=p.get("server_package_version"),
        )


@dataclass
class ActionResult:
    """Result of an action attempt."""

    success: bool
    action_id: Optional[str] = None
    error_message: Optional[str] = None

    def to_message(self) -> Message:
        """Convert to Message."""
        return Message(
            type=MessageType.ACTION_RESULT,
            payload={
                "success": self.success,
                "action_id": self.action_id,
                "error_message": self.error_message,
            },
        )


@dataclass
class JoinGameRequest:
    """Request to join a game."""

    player_name: str
    faction: Optional[str] = None  # Preferred faction, or None for auto-assign

    def to_message(self) -> Message:
        """Convert to Message."""
        return Message(
            type=MessageType.JOIN_GAME,
            payload={"player_name": self.player_name, "faction": self.faction},
        )

    @classmethod
    def from_message(cls, msg: Message) -> "JoinGameRequest":
        """Create from Message."""
        return cls(**msg.payload)


@dataclass
class PlayerInfo:
    """Information about a connected player."""

    player_id: str
    player_name: str
    faction: str
    connected: bool = True
    package_version: Optional[str] = None  # server hexes version (join ack only)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
