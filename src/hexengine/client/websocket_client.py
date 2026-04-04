"""
Browser-compatible WebSocket client using native browser WebSocket API.

Works in pyodide by using JavaScript WebSocket through js proxy.
"""

import json
import logging
from enum import Enum
from typing import Optional, Callable, Any
from dataclasses import asdict

from ..document import js, create_proxy
from ..state import GameState
from ..server.protocol import (
    Message, MessageType, ActionRequest, StateUpdate,
    JoinGameRequest, PlayerInfo
)


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
        self.player_id: Optional[str] = None
        self.player_name: Optional[str] = None
        self.faction: Optional[str] = None
        
        # Current game state (last received from server)
        self.game_state: Optional[GameState] = None
        self.sequence_number = 0
        
        # Last applied scenario map_display JSON (avoid reset_view on every state tick)
        self._applied_map_display_json: Optional[str] = None
        self._warned_stale_client = False

        # Callbacks
        self.on_state_update: Optional[Callable[[GameState], None]] = None
        self.on_map_display: Optional[Callable[[dict[str, Any]], None]] = None
        self.on_connection_change: Optional[Callable[[ConnectionState], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_action_result: Optional[Callable[[bool, Optional[str]], None]] = None
        self.on_player_joined: Optional[Callable[[PlayerInfo], None]] = None
        self.on_player_left: Optional[Callable[[PlayerInfo], None]] = None
        
        self.logger = logging.getLogger("websocket_client")
    
    def connect(self, player_name: str, preferred_faction: Optional[str] = None) -> None:
        """
        Connect to the game server and join a game.
        
        Args:
            player_name: Display name for this player
            preferred_faction: Preferred faction (or None for auto-assign)
        """
        if self.connection_state != ConnectionState.DISCONNECTED:
            self.logger.warning("Already connected or connecting")
            return
        
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
                player_name=player_name,
                faction=preferred_faction
            )
            
            self.logger.info(f"Connecting to {self.server_url}...")
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self._set_connection_state(ConnectionState.FAILED)
            self._handle_error(f"Connection failed: {e}")
    
    def disconnect(self) -> None:
        """Disconnect from the server."""
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
            player_id=self.player_id or "unknown"
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
        if hasattr(self, '_pending_join'):
            self._send_message(self._pending_join.to_message())
            delattr(self, '_pending_join')
    
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
        self.logger.error(f"WebSocket error: {event}")
        self._set_connection_state(ConnectionState.FAILED)
        self._handle_error("WebSocket error occurred")
    
    def _on_close(self, event) -> None:
        """Called when WebSocket closes."""
        self.logger.warning(f"WebSocket closed (code: {event.code})")
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

        if update.map_display is not None and self.on_map_display:
            sig = json.dumps(update.map_display, sort_keys=True)
            if sig != self._applied_map_display_json:
                self._applied_map_display_json = sig
                self.on_map_display(update.map_display)

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
    
    def _maybe_warn_server_newer(self, server_ver: Optional[str]) -> None:
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
        try:
            from .. import dev_console

            dev_console.set_status(msg)
        except Exception:
            pass

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
        from ..state.game_state import GameState, BoardState, TurnState, UnitState
        from ..hexes.types import Hex
        
        # Reconstruct units
        units = {}
        for unit_id, unit_data in state_dict.get("board", {}).get("units", {}).items():
            pos_data = unit_data["position"]
            units[unit_id] = UnitState(
                unit_id=unit_data["unit_id"],
                unit_type=unit_data["unit_type"],
                faction=unit_data["faction"],
                position=Hex(**pos_data),
                health=unit_data["health"],
                active=unit_data.get("active", True),
            )
        
        # Reconstruct locations (list form from server, or dict for backward compatibility)
        locations = {}
        raw_locations = state_dict.get("board", {}).get("locations", [])
        if isinstance(raw_locations, dict):
            # Legacy format: dict with Hex-like keys serialized by dataclasses
            raw_iter = raw_locations.values()
        else:
            raw_iter = raw_locations

        for loc in raw_iter:
            pos_data = loc["position"]
            pos = Hex(**pos_data)
            from ..state.game_state import LocationState

            locations[pos] = LocationState(
                position=pos,
                terrain_type=loc["terrain_type"],
                movement_cost=loc["movement_cost"],
            )

        # Reconstruct board
        board = BoardState(units=units, locations=locations)
        
        # Reconstruct turn
        turn_data = state_dict.get("turn", {})
        turn = TurnState(
            turn_number=turn_data.get("turn_number", 1),
            current_faction=turn_data.get("current_faction", "Red"),
            current_phase=turn_data.get("current_phase", "Movement"),
            phase_actions_remaining=turn_data.get("phase_actions_remaining", 2)
        )
        
        # Create game state
        return GameState(board=board, turn=turn)
