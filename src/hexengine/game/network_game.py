"""
Network-enabled Game class that sends actions to server.

This extends the base Game class to work with multiplayer by routing
all actions through a WebSocket connection to the server.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .. import dev_console
from ..client import LocalServerManager
from ..client.marker_manager import MarkerManager
from ..client.websocket_client import BrowserWebSocketClient, ConnectionState
from ..gamedef.builtin import (
    InterleavedTwoFactionGameDefinition,
    SequentialTwoFactionGameDefinition,
    StaticScheduleGameDefinition,
)
from ..gamedef.protocol import GameDefinition
from ..state import GameState
from ..state.snapshot import SNAPSHOT_FORMAT_VERSION, game_state_to_wire_dict
from .game import Game


def _game_definition_from_turn_rules_wire(wire: dict[str, Any]) -> GameDefinition:
    """Rebuild engine `GameDefinition` from `StateUpdate.turn_rules` (no title import)."""
    raw_entries = wire.get("entries")
    if isinstance(raw_entries, list) and raw_entries:
        budget = float(wire.get("movement_budget", 4.0))
        entries: list[dict[str, Any]] = []
        for row in raw_entries:
            if not isinstance(row, dict):
                continue
            entries.append(
                {
                    "faction": str(row["faction"]),
                    "phase": str(row["phase"]),
                    "max_actions": int(row["max_actions"]),
                }
            )
        if entries:
            return StaticScheduleGameDefinition(entries, movement_budget=budget)
    raw = wire.get("factions")
    if not isinstance(raw, list) or not raw:
        raise ValueError("turn_rules must include entries or legacy factions list")
    factions = tuple(str(f) for f in raw)
    sched = (wire.get("schedule") or "interleaved").strip().lower()
    budget = float(wire.get("movement_budget", 4.0))
    if sched == "sequential":
        return SequentialTwoFactionGameDefinition(
            factions=factions, movement_budget=budget
        )
    return InterleavedTwoFactionGameDefinition(
        factions=factions, movement_budget=budget
    )


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
        *,
        game_schedule: str = "interleaved",
    ):
        """
        Initialize network-enabled game.

        Args:
            server_url: URL of game server
            player_name: This player's display name
            preferred_faction: Preferred faction (or None for auto-assign)
            use_local_server: If True, start a local server for single-player
            game_schedule: `interleaved` or `sequential`; must match `hexserver --schedule`.
        """
        super().__init__()

        self._game_schedule = game_schedule.strip().lower()

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
        #: Title rules for `advance_turn`, filled from `StateUpdate.turn_rules`.
        self._title_game_definition: GameDefinition | None = None

        # Connection state
        self.connected = False
        self.my_faction: str | None = None

        self.logger = logging.getLogger("network_game")
        self.marker_mgr = MarkerManager(self.canvas)
        # Do not drive UI from local TurnManager; server state is authoritative.
        self.turn_manager.handlers.clear()

    def connect(self) -> bool:
        """
        Connect to the game server.

        Reconnecting the same client to the same match is supported; switching to a
        different title/scenario is assumed rare (full reload / prepared restart).

        Returns:
            True if connected successfully
        """
        try:
            # Drop any previous client so proxies/handlers are not orphaned
            if self.client is not None:
                self.client.disconnect()
                self.client = None
            # Re-learn schedule from the next StateUpdate.turn_rules (game switches are rare).
            self._title_game_definition = None

            preloaded_unit_graphics: dict[str, Any] | None = None
            preloaded_marker_graphics: dict[str, Any] | None = None
            preloaded_markers: list[dict[str, Any]] | None = None

            # Start local server if requested
            if self.use_local_server and not self.local_server:
                self.logger.info("Starting local server...")
                from ..gameroot import (
                    initial_turn_slot_for_game_definition,
                    load_game_definition_for_scenario,
                    resolve_scenario_path_with_game_root,
                    try_hexdemo_loaded_banner,
                )
                from ..scenarios import load_scenario
                from ..scenarios.loader import scenario_to_initial_state

                scenario_path = resolve_scenario_path_with_game_root()
                scenario_data = load_scenario(scenario_path)
                game_def = load_game_definition_for_scenario(
                    scenario_path, schedule=self._game_schedule
                )
                first = initial_turn_slot_for_game_definition(game_def)
                preloaded_unit_graphics = scenario_data.unit_graphics_to_wire_dict()
                preloaded_marker_graphics = getattr(
                    scenario_data, "marker_graphics_to_wire_dict", lambda: {}
                )()
                preloaded_markers = getattr(
                    scenario_data, "markers_to_wire_list", lambda: []
                )()
                initial_state = scenario_to_initial_state(
                    scenario_data,
                    initial_faction=first["faction"],
                    initial_phase=first["phase"],
                    phase_actions_remaining=int(first["max_actions"]),
                    schedule_index=0,
                )
                try_hexdemo_loaded_banner(scenario_path)
                self.local_server = LocalServerManager(
                    initial_state=initial_state,
                    map_display=scenario_data.map_display.to_wire_dict(),
                    global_styles=scenario_data.global_styles.to_wire_dict(),
                    unit_graphics=preloaded_unit_graphics,
                    marker_graphics=preloaded_marker_graphics,
                    markers=preloaded_markers,
                    game_definition=game_def,
                )
                if not self.local_server.start():
                    self.logger.error("Failed to start local server")
                    return False

                # Give server time to start (using setTimeout instead of asyncio.sleep)
                # Note: In browser, connection will be async via callbacks anyway

            # Title rules for advance_turn come from server StateUpdate.turn_rules (see
            # _handle_state_update). No per-connect filesystem preload: remote/Pyodide
            # clients often have no game pack on disk; switching games is out of scope.

            # Create client and set up callbacks
            self.client = BrowserWebSocketClient(self.server_url)

            self.client.on_state_update = self._handle_state_update
            self.client.on_map_display = self._on_map_display
            self.client.on_global_styles = self._on_global_styles
            self.client.on_unit_graphics = self._on_unit_graphics
            self.client.on_marker_graphics = self._on_marker_graphics
            self.client.on_markers = self._on_markers
            self.client.on_connection_change = self._handle_connection_change
            self.client.on_error = self._handle_error
            self.client.on_action_result = self._handle_action_result

            # Apply the same unit_graphics the server uses before the first StateUpdate
            # so the initial sync_from_state picks up scenario templates (not builtins only).
            if preloaded_unit_graphics is not None:
                self.display_mgr.apply_unit_graphics(preloaded_unit_graphics)
                self.client._applied_unit_graphics_json = json.dumps(
                    preloaded_unit_graphics, sort_keys=True, ensure_ascii=True
                )

            if preloaded_marker_graphics is not None:
                self.marker_mgr.apply_marker_graphics(preloaded_marker_graphics)
                self.client._applied_marker_graphics_json = json.dumps(
                    preloaded_marker_graphics, sort_keys=True, ensure_ascii=True
                )
            if preloaded_markers is not None:
                self.marker_mgr.sync_markers(preloaded_markers)

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

        self._title_game_definition = None
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
        from ..hexes.types import HexColRow
        from ..state.actions import (
            AddMarker,
            AddUnit,
            DeleteUnit,
            MoveMarker,
            MoveUnit,
            NextPhase,
            RemoveMarker,
            SpendAction,
        )

        if isinstance(action, AddMarker):
            cr = HexColRow.from_hex(action.position)
            return {
                "marker_id": action.marker_id,
                "marker_type": action.marker_type,
                "position": [cr.col, cr.row],
                "active": action.active,
            }
        if isinstance(action, RemoveMarker):
            return {"marker_id": action.marker_id}
        if isinstance(action, MoveMarker):
            fc = HexColRow.from_hex(action.from_hex)
            tc = HexColRow.from_hex(action.to_hex)
            return {
                "marker_id": action.marker_id,
                "from_position": [fc.col, fc.row],
                "to_position": [tc.col, tc.row],
            }
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
        self.display_mgr.adopt_hex_layout(self.action_mgr.current_state)

    def _on_unit_graphics(self, wire: dict[str, Any]) -> None:
        """Apply scenario unit graphics templates before state sync."""
        self.display_mgr.apply_unit_graphics(wire)

    def _on_marker_graphics(self, wire: dict[str, Any]) -> None:
        """Apply scenario marker graphics templates before state sync."""
        self.marker_mgr.apply_marker_graphics(wire)

    def _on_markers(self, wire: list[dict[str, Any]]) -> None:
        """Sync markers list from server (authoritative positions)."""
        self.marker_mgr.sync_markers(wire)

    def _handle_state_update(self, new_state: GameState) -> None:
        """
        Callback when server sends a state update.

        Args:
            new_state: New game state from server
        """
        if (
            self.client is not None
            and self.client.turn_rules is not None
            and self._title_game_definition is None
        ):
            try:
                self._title_game_definition = _game_definition_from_turn_rules_wire(
                    self.client.turn_rules
                )
            except Exception as e:
                self.logger.warning(
                    "Could not cache GameDefinition from server turn_rules: %s", e
                )

        self.logger.info(
            f"Received state update with {len(new_state.board.units)} units"
        )

        old_state = self.action_mgr.current_state

        # Drop any in-progress local drag/highlights — server state is authoritative
        # and stale selection caused inactive clients to run _unit_drag / clear churn.
        self._clear_drag_and_highlights()

        if old_state is not None:
            ot, nt = old_state.turn, new_state.turn
            if (
                ot.current_faction != nt.current_faction
                or ot.current_phase != nt.current_phase
            ):
                self.selection = None

        # Update local state (don't use ActionManager.execute - server is source of truth)
        self.action_mgr._current_state = new_state

        # Sync display to match new state
        self.display_mgr.sync_from_state(new_state)

        self._sync_turn_ui(new_state)

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
        dev_console.set_status(f"Server: {error}")
        # Invalid move uses "error", not action_result(success=False).
        self.display_mgr.refresh_unit_positions()

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
            if error_msg:
                dev_console.set_status(f"Server: {error_msg}")
            # Move (etc.) did not apply; preview may still follow the cursor transform.
            self.display_mgr.refresh_unit_positions()

    def is_my_turn(self) -> bool:
        """Check if it's currently this player's turn."""
        if not self.client:
            return False
        return self.client.is_my_turn()

    def _sync_turn_ui(self, state) -> None:
        """Turn display from replicated server state (not local TurnManager)."""
        from .turn_strip import (
            apply_turn_strip_faction,
            display_faction_name,
            display_phase_name,
        )

        faction = state.turn.current_faction
        phase = state.turn.current_phase
        actions = state.turn.phase_actions_remaining

        from ..document import element

        turn_bg = element("turn-display")
        if turn_bg:
            apply_turn_strip_faction(turn_bg, faction)

        turn_info = element("turn-info")
        if turn_info:
            turn_info.innerText = (
                f"{display_faction_name(faction)} - "
                f"{display_phase_name(phase)} (actions: {actions})"
            )

        advance_btn = element("advance-button")
        advance_btn.disabled = not self.is_my_turn()
        self.logger.warning(f"Advance button enabled: {self.is_my_turn()}")

        self.logger.debug(f"UI updated for {faction}-{phase}")

    def update_turn_display(self, faction=None, phase=None) -> None:
        """Use server-backed state instead of local TurnManager phases."""
        st = self.action_mgr.current_state
        if st is not None:
            self._sync_turn_ui(st)

    def advance_turn(self, _) -> None:
        """Send NextPhase derived from the same schedule as the server (not local TurnManager)."""
        from ..gamedef.builtin import advance_turn_action_for_state

        current_state = self.action_mgr.current_state
        if current_state is None:
            self.logger.warning("Cannot advance turn: no current state")
            return

        gd = self._title_game_definition
        if gd is None:
            self.logger.error(
                "Advance turn before turn schedule is known (missing StateUpdate.turn_rules); "
                "reconnect after the server has sent state."
            )
            dev_console.set_status("Advance turn: wait for sync, then try again.")
            return

        np = advance_turn_action_for_state(current_state, gd)
        self.logger.info(f"Advance turn (network): {np}")
        self._clear_drag_and_highlights()
        self.selection = None
        self.execute_action(np)

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
