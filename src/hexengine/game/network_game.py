"""
Network-enabled Game class that sends actions to server.

This extends the base Game class to work with multiplayer by routing
all actions through a WebSocket connection to the server.
"""

import logging
from typing import Optional

from ..client.browser_websocket_client import BrowserWebSocketClient, ConnectionState
from ..client import LocalServerManager
from ..state import GameState
from ..hexes.types import Hex
from .game import Game


class NetworkGame(Game):
    """
    Multiplayer-enabled game that communicates with a server.
    
    Key differences from base Game:
    - Actions are sent to server instead of executed locally
    - State updates come from server, not from local ActionManager
    - Server validates all actions and manages turn order
    - Works identically for single-player (local server) and multiplayer (remote server)
    """
    
    def __init__(self, 
                 server_url: str = "ws://localhost:8765",
                 player_name: str = "Player",
                 preferred_faction: Optional[str] = None,
                 use_local_server: bool = True):
        """
        Initialize network-enabled game.
        
        Args:
            server_url: URL of game server
            player_name: This player's display name
            preferred_faction: Preferred faction (or None for auto-assign)
            use_local_server: If True, start a local server for single-player
        """
        super().__init__()
        
        self.server_url = server_url
        self.player_name = player_name
        self.preferred_faction = preferred_faction
        self.use_local_server = use_local_server
        
        # Client connection
        self.client: Optional[BrowserWebSocketClient] = None
        self.local_server: Optional[LocalServerManager] = None
        
        # Connection state
        self.connected = False
        self.my_faction: Optional[str] = None
        
        self.logger = logging.getLogger("network_game")
    
    def connect(self) -> bool:
        """
        Connect to the game server.
        
        Returns:
            True if connected successfully
        """
        try:
            # Start local server if requested
            if self.use_local_server and not self.local_server:
                self.logger.info("Starting local server...")
                self.local_server = LocalServerManager(
                    initial_state=self.action_mgr.current_state
                )
                if not self.local_server.start():
                    self.logger.error("Failed to start local server")
                    return False
                
                # Give server time to start (using setTimeout instead of asyncio.sleep)
                # Note: In browser, connection will be async via callbacks anyway
            
            # Create client and set up callbacks
            self.client = BrowserWebSocketClient(self.server_url)
            
            self.client.on_state_update = self._handle_state_update
            self.client.on_connection_change = self._handle_connection_change
            self.client.on_error = self._handle_error
            self.client.on_action_result = self._handle_action_result
            
            # Connect to server (synchronous in browser)
            self.client.connect(
                player_name=self.player_name,
                preferred_faction=self.preferred_faction
            )
            
            # Connection happens asynchronously via callbacks
            self.logger.info("Connection initiated...")
            return True
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from the server."""
        if self.client:
            self.client.disconnect()
            self.client = None
        
        if self.local_server:
            self.local_server.stop()
            self.local_server = None
        
        self.connected = False
        self.logger.info("Disconnected")
    
    def execute_action(self, action) -> None:
        """
        Override: Send action to server instead of executing locally.
        
        Args:
            action: Action to execute (e.g., MoveUnit, DeleteUnit)
        """
        from ..document import js
        
        if not self.client or not self.connected:
            js.console.warn("Cannot execute action: not connected to server")
            return
        
        # Check if it's our turn (client-side validation for UX)
        if not self.client.is_my_turn():
            js.console.warn("Cannot execute action: not your turn")
            return
        
        # Serialize action to server format
        action_type = action.__class__.__name__
        params = self._serialize_action_params(action)
        
        # Send to server (synchronous in browser context)
        try:
            self.client.send_action(action_type, params)
            js.console.log(f"[NetworkGame] Sent {action_type} to server")
        except Exception as e:
            js.console.error(f"Failed to send action: {e}")
    
    def _serialize_action_params(self, action) -> dict:
        """
        Convert action to dict for network transmission.
        
        Args:
            action: Action instance
            
        Returns:
            Dictionary of action parameters
        """
        from ..state.actions import MoveUnit, DeleteUnit, AddUnit, SpendAction
        
        if isinstance(action, MoveUnit):
            return {
                "unit_id": action.unit_id,
                "from_hex": {"i": action.from_hex.i, "j": action.from_hex.j, "k": action.from_hex.k},
                "to_hex": {"i": action.to_hex.i, "j": action.to_hex.j, "k": action.to_hex.k}
            }
        elif isinstance(action, DeleteUnit):
            return {"unit_id": action.unit_id}
        elif isinstance(action, AddUnit):
            return {
                "unit_id": action.unit_id,
                "unit_type": action.unit_type,
                "faction": action.faction,
                "position": {"i": action.position.i, "j": action.position.j, "k": action.position.k},
                "health": action.health
            }
        elif isinstance(action, SpendAction):
            return {"amount": action.amount}
        else:
            self.logger.error(f"Unknown action type: {type(action)}")
            return {}
    
    def _handle_state_update(self, new_state: GameState) -> None:
        """
        Callback when server sends a state update.
        
        Args:
            new_state: New game state from server
        """
        from ..document import js
        js.console.log(f"[NetworkGame] Received state update with {len(new_state.board.units)} units")
        
        # Update local state (don't use ActionManager - server is source of truth)
        self.action_mgr._state = new_state
        
        # Sync display to match new state
        self.display_mgr.sync_from_state(new_state)
        
        # Update turn display
        faction = new_state.turn.current_faction
        phase = new_state.turn.current_phase
        actions = new_state.turn.phase_actions_remaining
        
        from ..document import element
        turn_bg = element("turn-display")
        if turn_bg:
            turn_bg.classList.remove("red", "blue")
            turn_bg.classList.add(faction.lower())
        
        turn_info = element("turn-info")
        if turn_info:
            turn_info.innerText = f"{faction}-{phase} (Actions: {actions})"
        
        js.console.log(f"[NetworkGame] UI updated for {faction}-{phase}")
    
    def _handle_connection_change(self, state: ConnectionState) -> None:
        """
        Callback when connection state changes.
        
        Args:
            state: New connection state
        """
        self.logger.info(f"Connection state: {state.value}")
        self.connected = (state == ConnectionState.CONNECTED)
        
        # TODO: Update UI to show connection state
    
    def _handle_error(self, error: str) -> None:
        """
        CaUpdate faction when connected
        if self.connected and self.client:
            self.my_faction = self.client.faction
            if self.my_faction:
                self.logger.info(f"Playing as {self.my_faction}")
        
        # llback when an error occurs.
        
        Args:
            error: Error message
        """
        self.logger.error(f"Server error: {error}")
        
        # TODO: Show error to user
    
    def _handle_action_result(self, success: bool, error_msg: Optional[str]) -> None:
        """
        Callback when server responds to an action we sent.
        
        Args:
            success: Whether the action succeeded
            error_msg: Error message if failed
        """
        if success:
            self.logger.debug("Action accepted by server")
        else:
            self.logger.warning(f"Action rejected: {error_msg}")
            # TODO: Show error to user
    
    def is_my_turn(self) -> bool:
        """Check if it's currently this player's turn."""
        if not self.client:
            return False
        return self.client.is_my_turn()
