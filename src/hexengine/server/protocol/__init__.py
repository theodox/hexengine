"""
Client/server communication protocol package.

This re-exports the public protocol surface from:
- `internals`: Message types, `Message`, registry/decorator helpers
- `client`: client -> server payload dataclasses
- `server`: server -> client payload dataclasses
"""

from __future__ import annotations

from .client import (
    ActionRequest,
    InspectRequest,
    JoinGameRequest,
    LeaveGameRequest,
    LoadSnapshotRequest,
    MapSelectionPreviewRequest,
    MarkerPreviewRequest,
    RedoRequest,
    UndoRequest,
    UnitPreviewRequest,
)
from .internals import (
    Message,
    WireMessageType,
    assert_wire_registry_covers_message_types,
    client_message,
    registered_message_types,
    server_message,
)
from .server import (
    ActionResult,
    CombatEventWire,
    MapSelectionPreviewWire,
    MarkerPreviewWire,
    PlayerInfo,
    PlayerJoinedWire,
    PlayerLeftWire,
    ServerError,
    ServerLogEvent,
    StateUpdate,
    UIPopupWire,
    UnitPreviewWire,
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
    "InspectRequest",
    "MapSelectionPreviewRequest",
    "MarkerPreviewRequest",
    "UnitPreviewRequest",
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
    "CombatEventWire",
    "MapSelectionPreviewWire",
    "MarkerPreviewWire",
    "UnitPreviewWire",
    "UIPopupWire",
]
