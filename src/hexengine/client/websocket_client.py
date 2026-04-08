"""
Browser-compatible WebSocket client using native browser WebSocket API.

Works in pyodide by using JavaScript WebSocket through js proxy.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from enum import Enum
from typing import Any

from .. import dev_console
from ..document import create_proxy, js
from ..server.protocol import (
    ActionRequest,
    JoinGameRequest,
    LoadSnapshotRequest,
    Message,
    MessageType,
    PlayerInfo,
    StateUpdate,
)
from ..state import GameState

# Browser WebSocket.readyState (MDN)
_WS_CONNECTING = 0
_WS_OPEN = 1
_WS_CLOSING = 2
_WS_CLOSED = 3

# How often to verify the socket is still OPEN while we believe we are connected.
_DEFAULT_HEALTH_CHECK_INTERVAL_MS = 10_000


class ConnectionState(Enum):
    """Current state of the WebSocket connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class BrowserWebSocketClient:
    """
    WebSocket client using browser's native WebSocket API.

    Works in pyodide by using JavaScript WebSocket through js proxy.
    """

    def __init__(self, server_url: str = "ws://localhost:8765"):
        """
        Initialize the WebSocket client.

        Args:
            server_url: URL of the game server (ws:// or wss://)
        """
        self.server_url = server_url
        self.connection_state = ConnectionState.DISCONNECTED
        self.websocket = None

        # Player info
        self.player_id: str | None = None
        self.player_name: str | None = None
        self.faction: str | None = None

        # Current game state (last received from server)
        self.game_state: GameState | None = None
        self.sequence_number = 0

        # Last applied scenario map_display JSON (avoid reset_view on every state tick)
        self._applied_map_display_json: str | None = None
        self._applied_global_styles_json: str | None = None
        self._applied_unit_graphics_json: str | None = None
        self._warned_stale_client = False

        # Callbacks
        self.on_state_update: Callable[[GameState], None] | None = None
        self.on_map_display: Callable[[dict[str, Any]], None] | None = None
        self.on_global_styles: Callable[[dict[str, Any]], None] | None = None
        self.on_unit_graphics: Callable[[dict[str, Any]], None] | None = None
        self.on_connection_change: Callable[[ConnectionState], None] | None = None
        self.on_error: Callable[[str], None] | None = None
        self.on_action_result: Callable[[bool, str | None], None] | None = None
        self.on_player_joined: Callable[[PlayerInfo], None] | None = None
        self.on_player_left: Callable[[PlayerInfo], None] | None = None

        self.logger = logging.getLogger("websocket_client")
        self._health_check_interval_id: Any = None
        self._health_check_proxy: Any = None

    def connect(self, player_name: str, preferred_faction: str | None = None) -> None:
        """
        Connect to the game server and join a game.

        Args:
            player_name: Display name for this player
            preferred_faction: Preferred faction (or None for auto-assign)
        """
        if self.connection_state not in (
            ConnectionState.DISCONNECTED,
            ConnectionState.FAILED,
        ):
            self.logger.warning("Already connected or connecting")
            return

        self._stop_connection_health_check()
        self._set_connection_state(ConnectionState.CONNECTING)
        self.player_name = player_name

        try:
            # Create browser WebSocket
            self.websocket = js.WebSocket.new(self.server_url)

            # Set up event handlers using create_proxy
            self.websocket.onopen = create_proxy(self._on_open)
            self.websocket.onmessage = create_proxy(self._on_message)
            self.websocket.onerror = create_proxy(self._on_error)
            self.websocket.onclose = create_proxy(self._on_close)

            # Store join request to send when connection opens
            self._pending_join = JoinGameRequest(
                player_name=player_name, faction=preferred_faction
            )

            self.logger.info(f"Connecting to {self.server_url}...")

        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self._set_connection_state(ConnectionState.FAILED)
            self._handle_error(f"Connection failed: {e}")

    def disconnect(self) -> None:
        """Disconnect from the server."""
        self._stop_connection_health_check()
        if self.websocket:
            # Send leave message
            try:
                message = Message(type=MessageType.LEAVE_GAME, payload={})
                self._send_message(message)
            except Exception:
                pass  # Best effort

            # Close connection
            self.websocket.close()
            self.websocket = None

        self._set_connection_state(ConnectionState.DISCONNECTED)
        self.logger.info("Disconnected from server")

    def send_action(self, action_type: str, params: dict[str, Any]) -> None:
        """
        Send an action request to the server.

        Args:
            action_type: Type of action (e.g., "MoveUnit", "DeleteUnit")
            params: Action parameters (e.g., {"unit_id": "...", "to_hex": {...}})
        """
        if not self.is_connected():
            self.logger.error("Cannot send action: not connected")
            return

        # Create action request
        request = ActionRequest(
            action_type=action_type,
            params=params,
            player_id=self.player_id or "unknown",
        )

        # Send to server
        self._send_message(request.to_message())
        self.logger.debug(f"Sent {action_type} action to server")

    def send_undo(self) -> None:
        """Send an undo request to the server."""
        if not self.is_connected():
            self.logger.error("Cannot send undo: not connected")
            return

        from ..server.protocol import UndoRequest

        request = UndoRequest(player_id=self.player_id or "unknown")
        self._send_message(request.to_message())
        self.logger.debug("Sent undo request to server")

    def send_redo(self) -> None:
        """Send a redo request to the server."""
        if not self.is_connected():
            self.logger.error("Cannot send redo: not connected")
            return

        from ..server.protocol import RedoRequest

        request = RedoRequest(player_id=self.player_id or "unknown")
        self._send_message(request.to_message())
        self.logger.debug("Sent redo request to server")

    def send_load_snapshot(self, game_state: dict[str, Any]) -> None:
        """Send a full game_state wire dict to replace server state."""
        if not self.is_connected():
            self.logger.error("Cannot load snapshot: not connected")
            return

        request = LoadSnapshotRequest(
            game_state=game_state,
            player_id=self.player_id or "unknown",
        )
        self._send_message(request.to_message())
        self.logger.debug("Sent load_snapshot request to server")

    def is_connected(self) -> bool:
        """Check if currently connected to server."""
        return self.connection_state == ConnectionState.CONNECTED

    def is_my_turn(self) -> bool:
        """Check if it's currently this player's turn."""
        if not self.game_state or not self.faction:
            return False
        return self.game_state.turn.current_faction == self.faction

    # Browser WebSocket event handlers

    def _on_open(self, event) -> None:
        """Called when WebSocket connection opens."""
        self.logger.info("WebSocket connected")
        self._set_connection_state(ConnectionState.CONNECTED)

        # Send pending join request
        if hasattr(self, "_pending_join"):
            self._send_message(self._pending_join.to_message())
            delattr(self, "_pending_join")

        self._start_connection_health_check()

    def _on_message(self, event) -> None:
        """Called when message received from server."""
        try:
            raw_message = event.data
            message = Message.from_json(raw_message)
            self._handle_message(message)
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")

    def _on_error(self, event) -> None:
        """Called on WebSocket error."""
        self._stop_connection_health_check()
        self.logger.error(f"WebSocket error: {event}")
        self._set_connection_state(ConnectionState.FAILED)
        self._handle_error("WebSocket error occurred")

    def _on_close(self, event) -> None:
        """Called when WebSocket closes."""
        self._stop_connection_health_check()
        msg = f"Disconnected (WebSocket closed, code {event.code})"
        self.logger.warning(msg)
        dev_console.set_status(msg)
        self.websocket = None
        self._set_connection_state(ConnectionState.DISCONNECTED)

    # Message handlers

    def _handle_message(self, message: Message) -> None:
        """Process a message received from the server."""
        try:
            if message.type == MessageType.STATE_UPDATE:
                self._handle_state_update(message)
            elif message.type == MessageType.ACTION_RESULT:
                self._handle_action_result(message)
            elif message.type == MessageType.PLAYER_JOINED:
                self._handle_player_joined(message)
            elif message.type == MessageType.PLAYER_LEFT:
                self._handle_player_left(message)
            elif message.type == MessageType.ERROR:
                self._handle_server_error(message)
            else:
                self.logger.warning(f"Unknown message type: {message.type}")

        except Exception as e:
            self.logger.error(f"Error handling message: {e}")

    def _handle_state_update(self, message: Message) -> None:
        """Handle a state update from the server."""
        update = StateUpdate.from_message(message)

        # Update sequence number
        if update.sequence_number <= self.sequence_number:
            self.logger.warning(f"Out-of-order state update: {update.sequence_number}")
        self.sequence_number = update.sequence_number

        if update.global_styles is not None and self.on_global_styles:
            sig = json.dumps(update.global_styles, sort_keys=True, ensure_ascii=True)
            if sig != self._applied_global_styles_json:
                self._applied_global_styles_json = sig
                try:
                    self.on_global_styles(update.global_styles)
                except Exception as e:
                    self.logger.error("on_global_styles failed: %s", e)

        if update.map_display is not None and self.on_map_display:
            sig = json.dumps(update.map_display, sort_keys=True, ensure_ascii=True)
            if sig != self._applied_map_display_json:
                self._applied_map_display_json = sig
                try:
                    self.on_map_display(update.map_display)
                except Exception as e:
                    self.logger.error("on_map_display failed: %s", e)

        if update.unit_graphics is not None and self.on_unit_graphics:
            sig = json.dumps(update.unit_graphics, sort_keys=True, ensure_ascii=True)
            if sig != self._applied_unit_graphics_json:
                self._applied_unit_graphics_json = sig
                try:
                    self.on_unit_graphics(update.unit_graphics)
                except Exception as e:
                    self.logger.error("on_unit_graphics failed: %s", e)

        self._maybe_warn_server_newer(update.server_package_version)

        # Reconstruct GameState from dict
        self.game_state = self._deserialize_game_state(update.game_state)

        # Extract faction if this is first state update
        if not self.faction and self.game_state:
            # Try to determine faction from player assignment
            # For now, we'll get it from the server's player_joined message
            pass

        # Notify callback
        if self.on_state_update:
            self.on_state_update(self.game_state)

    def _handle_action_result(self, message: Message) -> None:
        """Handle result of an action we sent."""
        payload = message.payload
        success = payload.get("success", False)
        error_msg = payload.get("error_message")

        if not success:
            self.logger.warning(f"Action failed: {error_msg}")

        if self.on_action_result:
            self.on_action_result(success, error_msg)

    def _maybe_warn_server_newer(self, server_ver: str | None) -> None:
        if not server_ver or self._warned_stale_client:
            return
        from ..package_version import hexes_package_version, server_is_newer_than_client

        client_ver = hexes_package_version()
        if not server_is_newer_than_client(server_ver, client_ver):
            return
        self._warned_stale_client = True
        msg = (
            f"Server package ({server_ver}) is newer than this client ({client_ver}). "
            "Refresh or install a matching wheel to avoid mismatches."
        )
        self.logger.warning(msg)
        dev_console.set_status(msg)

    def _handle_player_joined(self, message: Message) -> None:
        """Handle notification of another player joining."""
        raw = message.payload
        player = PlayerInfo(
            player_id=raw["player_id"],
            player_name=raw["player_name"],
            faction=raw["faction"],
            connected=raw.get("connected", True),
            package_version=raw.get("package_version"),
        )

        # Check if this is us
        if player.player_name == self.player_name and not self.faction:
            self.faction = player.faction
            self.player_id = player.player_id
            self.logger.info(f"Joined as {self.faction} (ID: {self.player_id})")
            self._maybe_warn_server_newer(player.package_version)
        else:
            self.logger.info(f"Player joined: {player.player_name} ({player.faction})")

        if self.on_player_joined:
            self.on_player_joined(player)

    def _handle_player_left(self, message: Message) -> None:
        """Handle notification of a player leaving."""
        raw = message.payload
        player = PlayerInfo(
            player_id=raw["player_id"],
            player_name=raw["player_name"],
            faction=raw["faction"],
            connected=raw.get("connected", True),
            package_version=raw.get("package_version"),
        )
        self.logger.info(f"Player left: {player.player_name}")

        if self.on_player_left:
            self.on_player_left(player)

    def _handle_server_error(self, message: Message) -> None:
        """Handle an error message from the server."""
        error = message.payload.get("error", "Unknown error")
        self.logger.error(f"Server error: {error}")
        self._handle_error(error)

    def _handle_error(self, error: str) -> None:
        """Trigger error callback."""
        if self.on_error:
            self.on_error(error)

    def _send_message(self, message: Message) -> None:
        """Send a message to the server."""
        if not self.websocket:
            raise RuntimeError("Not connected to server")

        json_str = message.to_json()
        self.websocket.send(json_str)

    def _set_connection_state(self, state: ConnectionState) -> None:
        """Update connection state and notify callback."""
        old_state = self.connection_state
        self.connection_state = state

        if old_state != state:
            self.logger.info(f"Connection state: {old_state.value} -> {state.value}")
            if self.on_connection_change:
                self.on_connection_change(state)

    def _deserialize_game_state(self, state_dict: dict[str, Any]) -> GameState:
        """Reconstruct GameState from dictionary."""
        from ..state.snapshot import game_state_from_wire_dict

        return game_state_from_wire_dict(state_dict)

    def _start_connection_health_check(self) -> None:
        """Periodic check that the browser socket is still OPEN (detects lost link if close lags)."""
        self._stop_connection_health_check()
        if self._health_check_proxy is None:
            self._health_check_proxy = create_proxy(self._connection_health_tick)
        try:
            self._health_check_interval_id = js.setInterval(
                self._health_check_proxy, _DEFAULT_HEALTH_CHECK_INTERVAL_MS
            )
        except Exception as e:
            self.logger.debug("Connection health check timer unavailable: %s", e)

    def _stop_connection_health_check(self) -> None:
        if self._health_check_interval_id is not None:
            try:
                js.clearInterval(self._health_check_interval_id)
            except Exception:
                pass
            self._health_check_interval_id = None

    def _connection_health_tick(self, *_args: Any) -> None:
        if self.connection_state != ConnectionState.CONNECTED:
            self._stop_connection_health_check()
            return
        ws = self.websocket
        if ws is None:
            msg = (
                "Connection lost: WebSocket missing while marked connected; "
                "server may be unreachable."
            )
            self.logger.error("Connection check: %s", msg)
            dev_console.set_status(msg)
            self._set_connection_state(ConnectionState.DISCONNECTED)
            self._stop_connection_health_check()
            return
        try:
            rs = int(ws.readyState)
        except Exception:
            return
        if rs == _WS_OPEN:
            return
        labels = {
            _WS_CONNECTING: "CONNECTING",
            _WS_OPEN: "OPEN",
            _WS_CLOSING: "CLOSING",
            _WS_CLOSED: "CLOSED",
        }
        log_detail = (
            f"WebSocket not open (readyState={rs} {labels.get(rs, '?')}); "
            "server unreachable or connection lost."
        )
        self.logger.error("Connection check: %s", log_detail)
        dev_console.set_status(
            f"Connection lost: socket {labels.get(rs, '?')} — server may be unreachable."
        )
        self.websocket = None
        self._set_connection_state(ConnectionState.DISCONNECTED)
        self._stop_connection_health_check()
