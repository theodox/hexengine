"""
WebSocket client for connecting to game server.

Handles connection, message sending/receiving, and automatic reconnection.
"""

import asyncio
import logging
from enum import Enum
from typing import Optional, Callable, Any
from dataclasses import asdict

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WebSocketClientProtocol = None

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


class WebSocketClient:
    """
    Client for connecting to a game server via WebSocket.
    
    Handles:
    - Connection management (connect, disconnect, reconnect)
    - Sending action requests to server
    - Receiving and processing state updates
    - Callback system for state changes and events
    """
    
    def __init__(self, server_url: str = "ws://localhost:8765"):
        """
        Initialize the WebSocket client.
        
        Args:
            server_url: URL of the game server (ws:// or wss://)
        """
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError(
                "websockets package not available. "
                "Install with: pip install websockets"
            )
        
        self.server_url = server_url
        self.connection_state = ConnectionState.DISCONNECTED
        self.websocket: Optional[WebSocketClientProtocol] = None
        
        # Player info
        self.player_id: Optional[str] = None
        self.player_name: Optional[str] = None
        self.faction: Optional[str] = None
        
        # Current game state (last received from server)
        self.game_state: Optional[GameState] = None
        self.sequence_number = 0
        
        # Callbacks
        self.on_state_update: Optional[Callable[[GameState], None]] = None
        self.on_connection_change: Optional[Callable[[ConnectionState], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_action_result: Optional[Callable[[bool, Optional[str]], None]] = None
        self.on_player_joined: Optional[Callable[[PlayerInfo], None]] = None
        self.on_player_left: Optional[Callable[[PlayerInfo], None]] = None
        
        self.logger = logging.getLogger("websocket_client")
        self._running = False
        self._receive_task: Optional[asyncio.Task] = None
    
    async def connect(self, player_name: str, preferred_faction: Optional[str] = None) -> bool:
        """
        Connect to the game server and join a game.
        
        Args:
            player_name: Display name for this player
            preferred_faction: Preferred faction (or None for auto-assign)
            
        Returns:
            True if connected successfully, False otherwise
        """
        if self.connection_state != ConnectionState.DISCONNECTED:
            self.logger.warning("Already connected or connecting")
            return False
        
        self._set_connection_state(ConnectionState.CONNECTING)
        self.player_name = player_name
        
        try:
            # Connect to WebSocket
            self.websocket = await websockets.connect(self.server_url)
            self.logger.info(f"Connected to {self.server_url}")
            
            # Send join game request
            join_request = JoinGameRequest(
                player_name=player_name,
                faction=preferred_faction
            )
            await self._send_message(join_request.to_message())
            
            # Start receiving messages
            self._running = True
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            self._set_connection_state(ConnectionState.CONNECTED)
            return True
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self._set_connection_state(ConnectionState.FAILED)
            self._handle_error(f"Connection failed: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from the server."""
        if self.websocket:
            self._running = False
            
            # Cancel receive task
            if self._receive_task:
                self._receive_task.cancel()
                try:
                    await self._receive_task
                except asyncio.CancelledError:
                    pass
            
            # Send leave message
            try:
                message = Message(type=MessageType.LEAVE_GAME, payload={})
                await self._send_message(message)
            except Exception:
                pass  # Best effort
            
            # Close connection
            await self.websocket.close()
            self.websocket = None
            
        self._set_connection_state(ConnectionState.DISCONNECTED)
        self.logger.info("Disconnected from server")
    
    async def send_action(self, action_type: str, params: dict[str, Any]) -> None:
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
        await self._send_message(request.to_message())
        self.logger.debug(f"Sent {action_type} action to server")
    
    def is_connected(self) -> bool:
        """Check if currently connected to server."""
        return self.connection_state == ConnectionState.CONNECTED
    
    def is_my_turn(self) -> bool:
        """Check if it's currently this player's turn."""
        if not self.game_state or not self.faction:
            return False
        return self.game_state.turn.current_faction == self.faction
    
    async def _receive_loop(self) -> None:
        """Background task that receives and processes messages from server."""
        try:
            while self._running and self.websocket:
                try:
                    raw_message = await self.websocket.recv()
                    message = Message.from_json(raw_message)
                    await self._handle_message(message)
                    
                except websockets.exceptions.ConnectionClosed:
                    self.logger.warning("Connection closed by server")
                    self._set_connection_state(ConnectionState.DISCONNECTED)
                    break
                    
        except asyncio.CancelledError:
            self.logger.debug("Receive loop cancelled")
        except Exception as e:
            self.logger.error(f"Error in receive loop: {e}")
            self._set_connection_state(ConnectionState.FAILED)
    
    async def _handle_message(self, message: Message) -> None:
        """
        Process a message received from the server.
        
        Args:
            message: Message to process
        """
        try:
            if message.type == MessageType.STATE_UPDATE:
                await self._handle_state_update(message)
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
    
    async def _handle_state_update(self, message: Message) -> None:
        """Handle a state update from the server."""
        update = StateUpdate.from_message(message)
        
        # Update sequence number
        if update.sequence_number <= self.sequence_number:
            self.logger.warning(f"Out-of-order state update: {update.sequence_number}")
        self.sequence_number = update.sequence_number
        
        # Reconstruct GameState from dict
        # This uses the from_dict method we'll need to add to GameState
        self.game_state = self._deserialize_game_state(update.game_state)
        
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
    
    def _handle_player_joined(self, message: Message) -> None:
        """Handle notification of another player joining."""
        player = PlayerInfo(**message.payload)
        self.logger.info(f"Player joined: {player.player_name} ({player.faction})")
        
        if self.on_player_joined:
            self.on_player_joined(player)
    
    def _handle_player_left(self, message: Message) -> None:
        """Handle notification of a player leaving."""
        player = PlayerInfo(**message.payload)
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
    
    async def _send_message(self, message: Message) -> None:
        """
        Send a message to the server.
        
        Args:
            message: Message to send
        """
        if not self.websocket:
            raise RuntimeError("Not connected to server")
        
        await self.websocket.send(message.to_json())
    
    def _set_connection_state(self, state: ConnectionState) -> None:
        """
        Update connection state and notify callback.
        
        Args:
            state: New connection state
        """
        old_state = self.connection_state
        self.connection_state = state
        
        if old_state != state:
            self.logger.info(f"Connection state: {old_state.value} -> {state.value}")
            if self.on_connection_change:
                self.on_connection_change(state)
    
    def _deserialize_game_state(self, state_dict: dict[str, Any]) -> GameState:
        """
        Reconstruct GameState from dictionary.
        
        Args:
            state_dict: Serialized state from server
            
        Returns:
            GameState instance
        """
        # Import here to avoid circular dependency
        from ..state.game_state import GameState, BoardState, TurnState
        from ..hexes.types import Hex
        
        # Reconstruct nested dataclasses
        # This is a simplified version - you may need to adjust based on your actual structure
        
        # Reconstruct units
        units = {}
        for unit_id, unit_data in state_dict.get("board", {}).get("units", {}).items():
            from ..state.game_state import UnitState
            pos_data = unit_data["position"]
            units[unit_id] = UnitState(
                unit_id=unit_data["unit_id"],
                unit_type=unit_data["unit_type"],
                faction=unit_data["faction"],
                position=Hex(**pos_data),
                health=unit_data["health"]
            )
        
        # Reconstruct board
        board = BoardState(units=units)
        
        # Reconstruct turn
        turn_data = state_dict.get("turn", {})
        turn = TurnState(
            turn_number=turn_data["turn_number"],
            current_faction=turn_data["current_faction"],
            actions_remaining=turn_data["actions_remaining"]
        )
        
        # Create game state
        return GameState(board=board, turn=turn)
