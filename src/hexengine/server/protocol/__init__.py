"""
Client/server communication protocol package.

This re-exports the public protocol surface from:
- `internals`: Message types, `Message`, registry/decorator helpers
- `client`: client -> server payload dataclasses
- `server`: server -> client payload dataclasses
"""

from __future__ import annotations

from .internals import (
    Message,
    WireMessageType,
    assert_wire_registry_covers_message_types,
    registered_message_types,
    client_message,
    server_message,
)
from .client import (
    ActionRequest,
    JoinGameRequest,
    LeaveGameRequest,
    LoadSnapshotRequest,
    RedoRequest,
    UndoRequest,
)
from .server import (
    ActionResult,
    PlayerInfo,
    PlayerJoinedWire,
    PlayerLeftWire,
    ServerError,
    ServerLogEvent,
    StateUpdate,
)

assert_wire_registry_covers_message_types()

__all__ = [
    # internals / core wire
    "WireMessageType",
    "Message",
    "client_message",
    "server_message",
    "registered_message_types",
    # client payloads
    "UndoRequest",
    "RedoRequest",
    "ActionRequest",
    "LoadSnapshotRequest",
    "JoinGameRequest",
    "LeaveGameRequest",
    # server payloads
    "StateUpdate",
    "ActionResult",
    "PlayerInfo",
    "PlayerJoinedWire",
    "PlayerLeftWire",
    "ServerError",
    "ServerLogEvent",
]

