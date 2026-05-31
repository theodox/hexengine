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
    ActionResult,
    CombatEventWire,
    InspectRequest,
    JoinGameRequest,
    LeaveGameRequest,
    LoadSnapshotRequest,
    MapSelectionPreviewWire,
    MarkerPreviewWire,
    Message,
    PlayerInfo,
    PlayerJoinedWire,
    PlayerLeftWire,
    ServerError,
    ServerLogEvent,
    StateUpdate,
    UIPopupWire,
    UnitPreviewWire,
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
        #: Last `turn_rules` dict from `hexengine.server.protocol.StateUpdate` (if any).
        self.turn_rules: dict[str, Any] | None = None
        #: Last StateUpdate.suggested_focus_unit_id (per-viewer hint from server).
        self.suggested_focus_unit_id: str | None = None
        #: Last StateUpdate.retreat_obligations (per-viewer obligations from server).
        self.retreat_obligations: dict[str, int] | None = None
        #: Last StateUpdate.interaction_messages (per-viewer transient UI messages).
        self.interaction_messages: list[dict[str, Any]] | None = None
        #: Last StateUpdate.map_overlays (per-viewer map-space overlay specs).
        self.map_overlays: list[dict[str, Any]] = []
        #: Last StateUpdate.primary_actions (per-viewer combat action buttons).
        self.primary_actions: list[dict[str, Any]] | None = None
        #: Last StateUpdate.interaction_panels (HTML shell + wired actions/inputs).
        self.interaction_panels: list[dict[str, Any]] | None = None
        #: Last StateUpdate.current_segment (per-viewer arc segment descriptor).
        self.current_segment: dict[str, Any] | None = None

        # Last applied scenario map_display JSON (avoid reset_view on every state tick)
        self._applied_map_display_json: str | None = None
        self._applied_global_styles_json: str | None = None
        self._applied_unit_graphics_json: str | None = None
        self._applied_marker_graphics_json: str | None = None
        self._warned_stale_client = False

        # Callbacks
        self.on_state_update: Callable[[GameState], None] | None = None
        self.on_map_display: Callable[[dict[str, Any]], None] | None = None
        self.on_global_styles: Callable[[dict[str, Any]], None] | None = None
        self.on_unit_graphics: Callable[[dict[str, Any]], None] | None = None
        self.on_marker_graphics: Callable[[dict[str, Any]], None] | None = None
        self.on_markers: Callable[[list[dict[str, Any]]], None] | None = None
        self.on_connection_change: Callable[[ConnectionState], None] | None = None
        self.on_error: Callable[[str], None] | None = None
        self.on_action_result: Callable[[bool, str | None], None] | None = None
        self.on_player_joined: Callable[[PlayerInfo], None] | None = None
        self.on_player_left: Callable[[PlayerInfo], None] | None = None
        self.on_ui_popup: Callable[[dict[str, Any]], None] | None = None
        self.on_marker_preview: Callable[[dict[str, Any]], None] | None = None
        self.on_unit_preview: Callable[[dict[str, Any]], None] | None = None
        self.on_map_selection_preview: Callable[[dict[str, Any]], None] | None = None

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
                message = LeaveGameRequest().to_message()
                self._send_message(message)
            except Exception:
                pass  # Best effort

            # Close connection
            self.websocket.close()
            self.websocket = None

        self._set_connection_state(ConnectionState.DISCONNECTED)
        self.turn_rules = None
        self.suggested_focus_unit_id = None
        self.retreat_obligations = None
        self.interaction_messages = None
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

    def send_inspect(
        self,
        target_kind: str,
        target_id: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        if not self.is_connected():
            return
        request = InspectRequest(
            target_kind=str(target_kind),
            target_id=str(target_id),
            context=dict(context) if isinstance(context, dict) else None,
        )
        self._send_message(request.to_message())

    def send_inform_popup(
        self,
        inform_kind: str,
        reason: str,
        *,
        hex_wire: dict[str, int] | None = None,
        unit_id: str | None = None,
    ) -> None:
        """INFORM lane: title ``inform_popup`` hook → ``ui_popup`` callout."""
        ctx: dict[str, Any] = {"inform_kind": str(inform_kind).strip()}
        if isinstance(hex_wire, dict):
            ctx["hex"] = dict(hex_wire)
        if unit_id is not None and str(unit_id).strip():
            ctx["unit_id"] = str(unit_id).strip()
        self.send_inspect("inform", str(reason).strip(), context=ctx)

    def send_marker_preview_request(self, marker_id: str, marker_type: str) -> None:
        if not self.is_connected():
            return
        from ..server.protocol import MarkerPreviewRequest

        req = MarkerPreviewRequest(
            marker_id=str(marker_id),
            marker_type=str(marker_type),
            request_id=str(getattr(self, "_preview_req_counter", 0) + 1),
        )
        self._preview_req_counter = int(req.request_id)
        self._send_message(req.to_message())

    def send_unit_preview_request(self, unit_id: str) -> None:
        if not self.is_connected():
            return
        from ..server.protocol import UnitPreviewRequest

        req = UnitPreviewRequest(
            unit_id=str(unit_id),
            request_id=str(getattr(self, "_preview_req_counter", 0) + 1),
        )
        self._preview_req_counter = int(req.request_id)
        self._send_message(req.to_message())

    def send_map_selection_preview_request(
        self,
        kind: str,
        draft: dict[str, Any],
        *,
        request_id: str = "",
    ) -> None:
        if not self.is_connected():
            return
        from ..server.protocol import MapSelectionPreviewRequest

        req = MapSelectionPreviewRequest(
            kind=str(kind),
            draft=dict(draft),
            request_id=request_id or str(getattr(self, "_preview_req_counter", 0) + 1),
        )
        self._preview_req_counter = int(req.request_id) if req.request_id.isdigit() else 0
        self._send_message(req.to_message())

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
            message = Message.try_from_json(raw_message)
            if message is None:
                return
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
            handler = _SERVER_INBOUND_HANDLERS.get(message.type)
            if handler is None:
                self.logger.warning(f"Unknown message type: {message.type}")
            else:
                handler(self, message)

        except Exception as e:
            self.logger.error(f"Error handling message: {e}")

    def _handle_state_update(self, message: Message) -> None:
        """Handle a state update from the server."""
        update = StateUpdate.from_message(message)
        if update.turn_rules is not None:
            self.turn_rules = update.turn_rules
        self.suggested_focus_unit_id = update.suggested_focus_unit_id
        self.retreat_obligations = (
            dict(update.retreat_obligations)
            if isinstance(update.retreat_obligations, dict)
            else None
        )
        raw_msgs = update.interaction_messages
        if raw_msgs is not None and not isinstance(raw_msgs, list):
            to_py = getattr(raw_msgs, "to_py", None)
            if callable(to_py):
                raw_msgs = to_py()
        self.interaction_messages = (
            [dict(m) for m in raw_msgs] if isinstance(raw_msgs, list) else None
        )
        if isinstance(self.interaction_messages, list):
            now_ms = int(js.Date.now())
            for m in self.interaction_messages:
                if isinstance(m, dict):
                    m.setdefault("_received_at_ms", now_ms)

        if update.map_overlays is None:
            self.map_overlays = []
        else:
            self.map_overlays = [
                dict(m) for m in update.map_overlays if isinstance(m, dict)
            ]

        if update.primary_actions is None:
            self.primary_actions = None
        else:
            self.primary_actions = [
                dict(m) for m in update.primary_actions if isinstance(m, dict)
            ]

        if update.interaction_panels is None:
            self.interaction_panels = None
        else:
            self.interaction_panels = [
                dict(m) for m in update.interaction_panels if isinstance(m, dict)
            ]

        if update.current_segment is None:
            self.current_segment = None
        elif isinstance(update.current_segment, dict):
            self.current_segment = dict(update.current_segment)
        else:
            self.current_segment = None

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

        if update.marker_graphics is not None and self.on_marker_graphics:
            sig = json.dumps(update.marker_graphics, sort_keys=True, ensure_ascii=True)
            if sig != self._applied_marker_graphics_json:
                self._applied_marker_graphics_json = sig
                try:
                    self.on_marker_graphics(update.marker_graphics)
                except Exception as e:
                    self.logger.error("on_marker_graphics failed: %s", e)

        if update.markers is not None and self.on_markers:
            try:
                self.on_markers(update.markers)
            except Exception as e:
                self.logger.error("on_markers failed: %s", e)

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
        result = ActionResult.from_message(message)
        success = result.success
        error_msg = result.error_message

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
        player = PlayerJoinedWire.from_message(message).to_player_info()

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
        player = PlayerLeftWire.from_message(message).to_player_info()
        self.logger.info(f"Player left: {player.player_name}")

        if self.on_player_left:
            self.on_player_left(player)

    def _handle_combat_event(self, message: Message) -> None:
        """Combat resolution / retreat obligation (per-player instruction)."""
        evt = CombatEventWire.from_message(message)
        line = f"combat [{evt.instruction}] {evt.attack_kind} → {evt.outcome}: {evt.message}"
        if evt.retreat_unit_id and evt.retreat_hexes_remaining is not None:
            line += (
                f" (unit {evt.retreat_unit_id}, {evt.retreat_hexes_remaining} hexes)"
            )
        dev_console.append_log_line(logging.INFO, line)
        if evt.instruction == "retreat_required":
            dev_console.set_status(evt.message)
        elif evt.instruction == "wait":
            dev_console.set_status(evt.message)
        else:
            dev_console.set_status("")

    def _handle_server_log(self, message: Message) -> None:
        """Append a server-originated log line to the dev console."""
        evt = ServerLogEvent.from_message(message)
        wire = str(evt.level).upper()
        level = getattr(logging, wire, None)
        if not isinstance(level, int):
            level = logging.INFO
        name = evt.logger
        body = evt.message
        if isinstance(name, str) and name:
            line = f"{name} | {body}"
        else:
            line = str(body)
        dev_console.append_log_line(level, line)

    def _handle_ui_popup(self, message: Message) -> None:
        evt = UIPopupWire.from_message(message)
        payload = {
            "text": evt.text,
            "html": evt.html,
            "hex": evt.hex,
            "kind": evt.kind,
            "ttl_ms": evt.ttl_ms,
            "css_class": evt.css_class,
        }
        if self.on_ui_popup:
            self.on_ui_popup(payload)

    def _handle_marker_preview(self, message: Message) -> None:
        from ..server.protocol import MarkerPreviewWire

        wire = MarkerPreviewWire.from_message(message)
        payload = {
            "marker_id": str(wire.marker_id),
            "hexes": list(wire.hexes) if isinstance(wire.hexes, list) else [],
            "css_class": wire.css_class,
            "request_id": str(getattr(wire, "request_id", "") or ""),
        }
        if self.on_marker_preview:
            self.on_marker_preview(payload)

    def _handle_unit_preview(self, message: Message) -> None:
        from ..server.protocol import UnitPreviewWire

        wire = UnitPreviewWire.from_message(message)
        payload = {
            "unit_id": str(wire.unit_id),
            "kind": str(wire.kind),
            "hexes": list(wire.hexes) if isinstance(wire.hexes, list) else [],
            "css_class": wire.css_class,
            "request_id": str(getattr(wire, "request_id", "") or ""),
            "through_hexes": (
                list(wire.through_hexes)
                if isinstance(getattr(wire, "through_hexes", None), list)
                else None
            ),
            "through_css_class": getattr(wire, "through_css_class", None),
        }
        if self.on_unit_preview:
            self.on_unit_preview(payload)

    def _handle_map_selection_preview(self, message: Message) -> None:
        from ..server.protocol import MapSelectionPreviewWire

        wire = MapSelectionPreviewWire.from_message(message)
        payload = {
            "kind": str(wire.kind),
            "status_text": str(wire.status_text),
            "confirm_enabled": bool(wire.confirm_enabled),
            "request_id": str(getattr(wire, "request_id", "") or ""),
            "valid_target_hexes": (
                list(wire.valid_target_hexes)
                if isinstance(wire.valid_target_hexes, list)
                else None
            ),
            "eligible_attacker_ids": (
                list(wire.eligible_attacker_ids)
                if isinstance(wire.eligible_attacker_ids, list)
                else None
            ),
            "commit_payload": (
                dict(wire.commit_payload)
                if isinstance(wire.commit_payload, dict)
                else None
            ),
            "panel_actions": (
                list(wire.panel_actions)
                if isinstance(wire.panel_actions, list)
                else None
            ),
            "legal_next_hexes": (
                list(wire.legal_next_hexes)
                if isinstance(getattr(wire, "legal_next_hexes", None), list)
                else None
            ),
            "preview_path_hexes": (
                list(wire.preview_path_hexes)
                if isinstance(getattr(wire, "preview_path_hexes", None), list)
                else None
            ),
            "through_hexes": (
                list(wire.through_hexes)
                if isinstance(getattr(wire, "through_hexes", None), list)
                else None
            ),
        }
        if self.on_map_selection_preview:
            self.on_map_selection_preview(payload)

    def _handle_server_error(self, message: Message) -> None:
        """Handle an error message from the server."""
        error = ServerError.from_message(message).error
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

        if not isinstance(state_dict, dict):
            to_py = getattr(state_dict, "to_py", None)
            if callable(to_py):
                state_dict = to_py()
        if not isinstance(state_dict, dict):
            raise TypeError("game_state wire payload must be a dict")
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


_ServerInboundHandler = Callable[[BrowserWebSocketClient, Message], None]

_SERVER_INBOUND_HANDLERS: dict[str, _ServerInboundHandler] = {
    StateUpdate.wire_type: BrowserWebSocketClient._handle_state_update,
    ActionResult.wire_type: BrowserWebSocketClient._handle_action_result,
    PlayerJoinedWire.wire_type: BrowserWebSocketClient._handle_player_joined,
    PlayerLeftWire.wire_type: BrowserWebSocketClient._handle_player_left,
    ServerError.wire_type: BrowserWebSocketClient._handle_server_error,
    ServerLogEvent.wire_type: BrowserWebSocketClient._handle_server_log,
    CombatEventWire.wire_type: BrowserWebSocketClient._handle_combat_event,
    UIPopupWire.wire_type: BrowserWebSocketClient._handle_ui_popup,
    MarkerPreviewWire.wire_type: BrowserWebSocketClient._handle_marker_preview,
    UnitPreviewWire.wire_type: BrowserWebSocketClient._handle_unit_preview,
    MapSelectionPreviewWire.wire_type: BrowserWebSocketClient._handle_map_selection_preview,
}
