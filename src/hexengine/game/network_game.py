"""
Network-enabled Game class that sends actions to server.

This extends the base Game class to work with multiplayer by routing
all actions through a WebSocket connection to the server.
"""

import json
import logging
from typing import Any

from ..client import LocalServerManager
from ..client.websocket_client import BrowserWebSocketClient, ConnectionState
from ..state import GameState
from ..state.snapshot import SNAPSHOT_FORMAT_VERSION, game_state_to_wire_dict
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

    def __init__(
        self,
        server_url: str = "ws://localhost:8765",
        player_name: str = "Player",
        preferred_faction: str | None = None,
        use_local_server: bool = True,
    ):
        """
        Initialize network-enabled game.

        Args:
            server_url: URL of game server
            player_name: This player's display name
            preferred_faction: Preferred faction (or None for auto-assign)
            use_local_server: If True, start a local server for single-player
        """
        super().__init__()

        self.logger = logging.getLogger("network_game")
        self.logger.info(
            f"NetworkGame.__init__ - action_mgr after super().__init__(): {self.action_mgr}"
        )

        self.server_url = server_url
        self.player_name = player_name
        self.preferred_faction = preferred_faction
        self.use_local_server = use_local_server

        # Client connection
        self.client: BrowserWebSocketClient | None = None
        self.local_server: LocalServerManager | None = None

        # Connection state
        self.connected = False
        self.my_faction: str | None = None

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
                from ..scenarios.loader import scenario_to_initial_state
                from ..scenarios.parse import (
                    load_scenario,
                    resolve_scenario_path_for_server,
                )

                scenario_path = resolve_scenario_path_for_server()
                scenario_data = load_scenario(scenario_path)
                initial_state = scenario_to_initial_state(
                    scenario_data,
                    initial_faction="Red",
                    initial_phase="Movement",
                    phase_actions_remaining=2,
                )
                self.local_server = LocalServerManager(
                    initial_state=initial_state,
                    map_display=scenario_data.map_display.to_wire_dict(),
                    global_styles=scenario_data.global_styles.to_wire_dict(),
                    unit_graphics=scenario_data.unit_graphics_to_wire_dict(),
                )
                if not self.local_server.start():
                    self.logger.error("Failed to start local server")
                    return False

                # Give server time to start (using setTimeout instead of asyncio.sleep)
                # Note: In browser, connection will be async via callbacks anyway

            # Create client and set up callbacks
            self.client = BrowserWebSocketClient(self.server_url)

            self.client.on_state_update = self._handle_state_update
            self.client.on_map_display = self._on_map_display
            self.client.on_global_styles = self._on_global_styles
            self.client.on_unit_graphics = self._on_unit_graphics
            self.client.on_connection_change = self._handle_connection_change
            self.client.on_error = self._handle_error
            self.client.on_action_result = self._handle_action_result

            # Connect to server (synchronous in browser)
            self.client.connect(
                player_name=self.player_name, preferred_faction=self.preferred_faction
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

        if not self.client or not self.connected:
            self.logger.warning("Cannot execute action: not connected to server")
            return

        # Check if it's our turn (client-side validation for UX)
        if not self.client.is_my_turn():
            current_faction = (
                self.client.game_state.turn.current_faction
                if self.client.game_state
                else "unknown"
            )
            my_faction = self.client.faction if self.client.faction else "unknown"
            self.logger.warning(
                f"Cannot execute action: not your turn (current: {current_faction}, you: {my_faction})"
            )
            return

        # Serialize action to server format
        action_type = action.__class__.__name__
        params = self._serialize_action_params(action)

        # Send to server (synchronous in browser context)
        try:
            self.client.send_action(action_type, params)
            self.logger.info(f"Sent {action_type} to server")
        except Exception as e:
            self.logger.error(f"Failed to send action: {e}")

    def _serialize_action_params(self, action) -> dict:
        """
        Convert action to dict for network transmission.

        Args:
            action: Action instance

        Returns:
            Dictionary of action parameters
        """
        from ..state.actions import (
            AddUnit,
            DeleteUnit,
            MoveUnit,
            NextPhase,
            SpendAction,
        )

        if isinstance(action, MoveUnit):
            return {
                "unit_id": action.unit_id,
                "from_hex": {
                    "i": action.from_hex.i,
                    "j": action.from_hex.j,
                    "k": action.from_hex.k,
                },
                "to_hex": {
                    "i": action.to_hex.i,
                    "j": action.to_hex.j,
                    "k": action.to_hex.k,
                },
            }
        elif isinstance(action, DeleteUnit):
            return {"unit_id": action.unit_id}
        elif isinstance(action, AddUnit):
            return {
                "unit_id": action.unit_id,
                "unit_type": action.unit_type,
                "faction": action.faction,
                "position": {
                    "i": action.position.i,
                    "j": action.position.j,
                    "k": action.position.k,
                },
                "health": action.health,
            }
        elif isinstance(action, SpendAction):
            return {"amount": action.amount}
        elif isinstance(action, NextPhase):
            return {
                "new_faction": action.new_faction,
                "new_phase": action.new_phase,
                "max_actions": action.max_actions,
            }
        else:
            self.logger.error(f"Unknown action type: {type(action)}")
            return {}

    def _on_global_styles(self, wire: dict[str, Any]) -> None:
        """Apply global + scenario CSS before map / units (runs from websocket client)."""
        from ..client.global_styles import apply_global_styles_safe

        apply_global_styles_safe(wire)

    def _on_map_display(self, config: dict[str, Any]) -> None:
        """Apply scenario map presentation before state sync (runs from websocket client)."""
        self.canvas.apply_map_display(config)
        self.display_mgr.adopt_hex_layout()

    def _on_unit_graphics(self, wire: dict[str, Any]) -> None:
        """Apply scenario unit graphics templates before state sync."""
        self.display_mgr.apply_unit_graphics(wire)

    def _handle_state_update(self, new_state: GameState) -> None:
        """
        Callback when server sends a state update.

        Args:
            new_state: New game state from server
        """
        self.logger.info(
            f"Received state update with {len(new_state.board.units)} units"
        )

        # Drop any in-progress local drag/highlights — server state is authoritative
        # and stale selection caused inactive clients to run _unit_drag / clear churn.
        self._clear_drag_and_highlights()

        # Update local state (don't use ActionManager.execute - server is source of truth)
        self.action_mgr._current_state = new_state

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

        advance_btn = element("advance-button")
        advance_btn.disabled = not self.is_my_turn()
        self.logger.warning(f"Advance button enabled: {self.is_my_turn()}")

        self.logger.debug(f"UI updated for {faction}-{phase}")

    def _handle_connection_change(self, state: ConnectionState) -> None:
        """
        Callback when connection state changes.

        Args:
            state: New connection state
        """
        self.logger.info(f"Connection state: {state.value}")
        self.connected = state == ConnectionState.CONNECTED

        # TODO: Update UI to show connection state

    def _handle_error(self, error: str) -> None:
        """
        Callback when an error occurs.

        Args:
            error: Error message
        """
        self.logger.error(f"Server error: {error}")

        # TODO: Show error to user

    def _handle_action_result(self, success: bool, error_msg: str | None) -> None:
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

    # Override undo/redo to send requests to server instead of local execution
    def undo(self) -> None:
        """Override: Send undo request to server instead of executing locally."""
        if not self.client or not self.connected:
            self.logger.warning("Cannot undo: not connected to server")
            return

        try:
            self.client.send_undo()
            self.logger.info("Sent undo request to server")
        except Exception as e:
            self.logger.error(f"Failed to send undo request: {e}")

    def redo(self) -> None:
        """Override: Send redo request to server instead of executing locally."""
        if not self.client or not self.connected:
            self.logger.warning("Cannot redo: not connected to server")
            return

        try:
            self.client.send_redo()
            self.logger.info("Sent redo request to server")
        except Exception as e:
            self.logger.error(f"Failed to send redo request: {e}")

    def save_snapshot_dict(self) -> dict[str, Any]:
        """Build a versioned snapshot dict from the last server state on this client."""
        if not self.client or self.client.game_state is None:
            raise RuntimeError("No game state to save (not connected or no state yet)")
        return {
            "format_version": SNAPSHOT_FORMAT_VERSION,
            "game_state": game_state_to_wire_dict(self.client.game_state),
        }

    def save_snapshot_json(self) -> str:
        """JSON string for a versioned snapshot (indent=2)."""
        return json.dumps(self.save_snapshot_dict(), indent=2)

    def load_snapshot_dict(self, d: dict[str, Any]) -> None:
        """Send a snapshot dict to the server (format_version must be supported)."""
        if not self.client or not self.connected:
            raise RuntimeError("Cannot load snapshot: not connected")

        fv = d.get("format_version", SNAPSHOT_FORMAT_VERSION)
        if fv != SNAPSHOT_FORMAT_VERSION:
            raise ValueError(f"Unsupported snapshot format_version: {fv}")
        gs = d.get("game_state")
        if not isinstance(gs, dict):
            raise ValueError("snapshot missing game_state dict")

        self.client.send_load_snapshot(gs)
        self.logger.info("Sent load_snapshot to server")

    def load_snapshot_json(self, text: str) -> None:
        """Parse JSON and send load_snapshot to the server."""
        self.load_snapshot_dict(json.loads(text))
