from __future__ import annotations

import json
import logging
from typing import Any

from .. import dev_console
from ..client import DisplayManager, LocalServerManager, UIState
from ..client.marker_manager import MarkerManager
from ..client.websocket_client import BrowserWebSocketClient, ConnectionState
from ..document import create_proxy, element, js
from ..gamedef.builtin import (
    InterleavedTwoFactionGameDefinition,
    SequentialTwoFactionGameDefinition,
    StaticScheduleGameDefinition,
)
from ..gamedef.protocol import GameDefinition
from ..map import Map
from ..state import ActionManager, GameState
from ..state.snapshot import SNAPSHOT_FORMAT_VERSION, game_state_to_wire_dict
from ..ui.popups import PopupManager
from .board import GameBoard
from .events import Hotkey, HotkeyHandlerMixin, Modifiers, MouseEventHandlerMixin
from .history import GameHistoryMixin
from .turn_strip import (
    apply_turn_strip_faction,
    display_faction_name,
    display_phase_name,
)

# Screen-space pan per arrow key when zoomed in; Shift multiplies step.
_PAN_KEY_STEP = 48
_PAN_KEY_SHIFT_MULT = 3


def _game_definition_from_turn_rules_wire(wire: dict[str, Any]) -> GameDefinition:
    """Rebuild engine `GameDefinition` from `StateUpdate.turn_rules` (no title import)."""
    raw_attr = wire.get("movement_budget_attribute")
    per_kw: dict[str, Any] = {}
    if isinstance(raw_attr, str) and raw_attr.strip():
        per_kw["per_unit_movement_attribute"] = raw_attr.strip()

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
            return StaticScheduleGameDefinition(
                entries, movement_budget=budget, **per_kw
            )
    raw = wire.get("factions")
    if not isinstance(raw, list) or not raw:
        raise ValueError("turn_rules must include entries or legacy factions list")
    factions = tuple(str(f) for f in raw)
    sched = (wire.get("schedule") or "interleaved").strip().lower()
    budget = float(wire.get("movement_budget", 4.0))
    if sched == "sequential":
        return SequentialTwoFactionGameDefinition(
            factions=factions, movement_budget=budget, **per_kw
        )
    return InterleavedTwoFactionGameDefinition(
        factions=factions, movement_budget=budget, **per_kw
    )


class Game(MouseEventHandlerMixin, HotkeyHandlerMixin, GameHistoryMixin):
    """
    Browser session: map, units, UI, and a WebSocket client to an authoritative server.

    Match state and turn order always come from the server (embedded local server for
    solo play, or a remote URL for multiplayer).
    """

    def __init__(
        self,
        server_url: str = "ws://localhost:8765",
        player_name: str = "Player",
        preferred_faction: str | None = None,
        use_local_server: bool = True,
        *,
        game_schedule: str = "interleaved",
    ) -> None:
        self.running = True
        container = element("map-container")
        map = element("map-canvas")
        terrain = element("map-terrain")
        svg = element("map-svg")
        markers = element("map-markers")
        units = element("map-units")
        action_button = element("advance-button")
        action_button.onclick = self.advance_turn
        self.popup_manager = PopupManager(container)

        assert map is not None, "Map canvas element not found"
        assert svg is not None, "Map SVG element not found"
        self.canvas = Map(container, map, terrain, svg, markers, units)
        self.board = GameBoard(self.canvas)

        initial_state = GameState.create_empty(
            initial_faction="union",
            initial_phase="Move",
            phase_actions_remaining=2,
            schedule_index=0,
        )
        self.action_mgr = ActionManager(initial_state)
        self.logger = logging.getLogger("game")
        self.logger.info(f"action_mgr created: {self.action_mgr}")

        self.ui_state = UIState()
        self.display_mgr = DisplayManager(self.canvas, self.board)

        # Connect display manager as observer to sync on state changes
        self.action_mgr.add_observer(self.display_mgr.sync_from_state)

        # TODO: Sync initial display from state once units are added via new system
        # self.display_mgr.sync_from_state(self.action_mgr.current_state)

        self.click_time = 0
        self.last_click_time = 0
        self.drag_start = (0, 0)
        self.drag_end = (0, 0)
        #: Own unit id selected for adjacent attack (network / combat phase UX).
        self.pending_attack_attacker_id: str | None = None

        self.logger = logging.getLogger("game")
        self.logger.info("Game initialized")

        self.logger.info(
            f"[Game.__init__] Registering on_mouse_down: {self.on_mouse_down}"
        )
        self.canvas.on_mouse_down < self.on_mouse_down
        self.logger.info("[Game.__init__] Registered on_mouse_down")

        self.logger.info(f"[Game.__init__] Registering on_mouse_up: {self.on_mouse_up}")
        self.canvas.on_mouse_up < self.on_mouse_up
        self.logger.info("[Game.__init__] Registered on_mouse_up")

        self.logger.info(f"[Game.__init__] Registering on_drag: {self.on_drag}")
        self.canvas.on_drag < self.on_drag
        self.logger.info("[Game.__init__] Registered on_drag")

        self._register_hotkeys()

        self._game_schedule = game_schedule.strip().lower()
        self.server_url = server_url
        self.player_name = player_name
        self.preferred_faction = preferred_faction
        self.use_local_server = use_local_server
        self.client: BrowserWebSocketClient | None = None
        self.local_server: LocalServerManager | None = None
        self._title_game_definition: GameDefinition | None = None
        self.connected = False
        self.marker_mgr = MarkerManager(self.canvas)

        # Register resize handler to refresh map on window resize/zoom
        js.window.addEventListener("resize", create_proxy(self._handle_resize))
        self.logger.info("Registered window resize handler")

        # Register zoom and pan handlers
        self._is_panning = False
        self._pan_start_x = 0
        self._pan_start_y = 0
        self._space_pressed = False

        container.addEventListener("wheel", create_proxy(self._handle_wheel), False)
        js.window.addEventListener("keydown", create_proxy(self._handle_keydown))
        js.window.addEventListener("keyup", create_proxy(self._handle_keyup))
        self.logger.info("Registered zoom and pan handlers")

    def _handle_resize(self, event) -> None:
        """
        Handle window resize and zoom events.
        Refreshes the map canvas; pan/zoom are applied on layer roots, so unit
        transforms (map-space) stay valid.
        """
        self.logger.info("Window resized, refreshing map")
        self.canvas.refresh()
        if self.action_mgr is not None:
            self.display_mgr.redraw_terrain_overlay(self.action_mgr.current_state)

    def _handle_wheel(self, event) -> None:
        """
        Handle mouse wheel for zooming.
        """
        event.preventDefault()

        # Get mouse position relative to container
        rect = self.canvas._container.getBoundingClientRect()
        mouse_x = event.clientX - rect.left
        mouse_y = event.clientY - rect.top

        # Zoom in or out based on wheel delta
        zoom_speed = 0.001
        delta = -event.deltaY * zoom_speed

        self.canvas.adjust_zoom(delta, mouse_x, mouse_y)

    def _handle_keydown(self, event) -> None:
        """
        Handle keydown events for pan mode.
        """
        if event.key == " " or event.code == "Space":
            self._space_pressed = True
            # Change cursor to indicate pan mode
            self.canvas._container.style.cursor = "grab"

    def _handle_keyup(self, event) -> None:
        """
        Handle keyup events.
        """
        if event.key == " " or event.code == "Space":
            self._space_pressed = False
            self._is_panning = False
            # Restore cursor
            self.canvas._container.style.cursor = "default"

    # these are delegated to the board instance, but
    # exposed here for convenience
    @property
    def selection(self):
        return self.board.selection

    @property
    def layout(self):
        return self.canvas.hex_layout

    @selection.setter
    def selection(self, value):
        if self.board.selection:
            self.board.selection.hilited = False
        self.board.selection = value
        if self.board.selection:
            self.board.selection.hilited = True

    def add_unit(self, unit) -> None:
        self.board.add_unit(unit)

    def remove_unit(self, unit) -> None:
        self.board.remove_unit(unit)

    def pan_view(self, delta_x: float, delta_y: float) -> None:
        """Pan the map in screen pixels (CSS transform on layers; units stay in map space)."""
        self.canvas.adjust_pan(delta_x, delta_y)

    def on_key_down(self, event) -> None:
        key = event.key.lower()
        modifiers = Modifiers.from_event(event)
        if key in ("arrowleft", "arrowright", "arrowup", "arrowdown"):
            if self.canvas.zoom_level > 1.01:
                step = _PAN_KEY_STEP * (
                    _PAN_KEY_SHIFT_MULT if modifiers & Modifiers.SHIFT else 1
                )
                deltas = {
                    "arrowleft": (-step, 0),
                    "arrowright": (step, 0),
                    "arrowup": (0, -step),
                    "arrowdown": (0, step),
                }
                self.pan_view(*deltas[key])
                event.preventDefault()
                return
        HotkeyHandlerMixin.on_key_down(self, event)

    @Hotkey("delete", Modifiers.NONE)
    def delete_selected_unit(self) -> None:
        if self.ui_state.selected_unit_id:
            from ..state.actions import DeleteUnit

            action = DeleteUnit(self.ui_state.selected_unit_id)
            self.execute_action(action)

            # Clear UI state
            self.ui_state.end_drag()
            self.display_mgr.clear_highlights()

            self.logger.info(f"Deleted unit {self.ui_state.selected_unit_id}")
        else:
            self.logger.debug("No unit selected to delete")

    @Hotkey("enter", Modifiers.NONE)
    def popup_selected_unit_info(self) -> None:
        if self.selection:
            loc = self.layout.hex_to_pixel(self.selection.position)
            self.popup_manager.create_popup(
                f"{self.selection.unit_id} @ {self.selection.faction}", loc
            )
            self.logger.info(f"Showing info for unit {self.selection.unit_id}")
        else:
            self.popup_manager.clear()
            self.logger.debug("No unit selected to show info")

    @Hotkey("escape", Modifiers.NONE)
    def clear_selection(self) -> None:
        self.popup_manager.clear()

    @Hotkey("r", Modifiers.NONE)
    def reset_view(self) -> None:
        """Reset zoom and pan to default."""
        self.canvas.reset_view()
        self.logger.info("View reset to default")

    @Hotkey("t", Modifiers.NONE)
    def toggle_terrain_overlay(self) -> None:
        """Toggle terrain tint layer (console: `set_terrain_overlay` / `terrain_overlay_visible()`)."""
        self.canvas.set_terrain_overlay_visible(not self.canvas.terrain_overlay_visible)

    # ===== SERVER SESSION (WebSocket) =====

    def connect(self) -> bool:
        """
        Connect to the game server.

        Reconnecting the same client to the same match is supported; switching to a
        different title/scenario is assumed rare (full reload / prepared restart).
        """
        try:
            if self.client is not None:
                self.client.disconnect()
                self.client = None
            self._title_game_definition = None

            preloaded_unit_graphics: dict[str, Any] | None = None
            preloaded_marker_graphics: dict[str, Any] | None = None
            preloaded_markers: list[dict[str, Any]] | None = None

            if self.use_local_server and not self.local_server:
                self.logger.info("Starting local server...")
                from ..gameroot import (
                    initial_turn_slot_for_game_definition,
                    load_game_definition_for_scenario,
                    resolve_scenario_path_with_game_root,
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
                    game_definition=game_def,
                )
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

            self.client.connect(
                player_name=self.player_name, preferred_faction=self.preferred_faction
            )

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
        """Send an action to the server (state updates come back asynchronously)."""
        if not self.client or not self.connected:
            self.logger.warning("Cannot execute action: not connected to server")
            return

        from ..state.actions import MoveUnit

        allow = self.client.is_my_turn()
        if not allow and isinstance(action, MoveUnit) and self.client.game_state:
            rem = self.retreat_obligation_hexes_remaining(
                self.client.game_state, action.unit_id
            )
            if rem is not None:
                allow = True
        if not allow:
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

        action_type = action.__class__.__name__
        params = self._serialize_action_params(action)

        try:
            self.client.send_action(action_type, params)
            self.logger.info(f"Sent {action_type} to server")
        except Exception as e:
            self.logger.error(f"Failed to send action: {e}")

    def _serialize_action_params(self, action) -> dict[str, Any]:
        """Convert action to dict for network transmission."""
        from ..hexes.types import HexColRow
        from ..state.actions import (
            AddMarker,
            AddUnit,
            Attack,
            DeleteUnit,
            MoveMarker,
            MoveUnit,
            NextPhase,
            PatchUnitAttributes,
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
        if isinstance(action, Attack):
            return {
                "attack_kind": action.attack_kind,
                "attacker_id": action.attacker_id,
                "defender_id": action.defender_id,
            }
        if isinstance(action, DeleteUnit):
            return {"unit_id": action.unit_id}
        if isinstance(action, AddUnit):
            out: dict[str, Any] = {
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
            if action.stack_index is not None:
                out["stack_index"] = action.stack_index
            if action.graphics is not None:
                out["graphics"] = action.graphics
            if action.attributes:
                out["attributes"] = dict(action.attributes)
            return out
        if isinstance(action, PatchUnitAttributes):
            return {
                "unit_id": action.unit_id,
                "patch": dict(action.patch),
                "remove_keys": list(action.remove_keys),
            }
        if isinstance(action, SpendAction):
            return {"amount": action.amount}
        if isinstance(action, NextPhase):
            return {
                "new_faction": action.new_faction,
                "new_phase": action.new_phase,
                "max_actions": action.max_actions,
                "new_schedule_index": action.new_schedule_index,
            }
        self.logger.error(f"Unknown action type: {type(action)}")
        return {}

    def _on_global_styles(self, wire: dict[str, Any]) -> None:
        from ..client.global_styles import apply_global_styles_safe

        apply_global_styles_safe(wire)

    def _on_map_display(self, config: dict[str, Any]) -> None:
        self.canvas.apply_map_display(config)
        self.display_mgr.adopt_hex_layout(self.action_mgr.current_state)

    def _on_unit_graphics(self, wire: dict[str, Any]) -> None:
        self.display_mgr.apply_unit_graphics(wire)

    def _on_marker_graphics(self, wire: dict[str, Any]) -> None:
        self.marker_mgr.apply_marker_graphics(wire)

    def _on_markers(self, wire: list[dict[str, Any]]) -> None:
        self.marker_mgr.sync_markers(wire)

    def _handle_state_update(self, new_state: GameState) -> None:
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
        self._maybe_warn_missing_title_sync()

        self.logger.info(
            f"Received state update with {len(new_state.board.units)} units"
        )

        old_state = self.action_mgr.current_state

        self._clear_drag_and_highlights()

        if old_state is not None:
            ot, nt = old_state.turn, new_state.turn
            if (
                ot.current_faction != nt.current_faction
                or ot.current_phase != nt.current_phase
            ):
                self.selection = None

        self.action_mgr._current_state = new_state

        self.display_mgr.sync_from_state(new_state)

        self._sync_turn_ui(new_state)
        self._apply_focus_unit_after_state_sync(new_state)

    def _maybe_warn_missing_title_sync(self) -> None:
        """
        Dev guardrail: warn when the server advertises a contract feature but the
        corresponding per-update field is missing.
        """
        import os

        if os.getenv("HEXENGINE_STRICT_TITLE_SYNC", "").strip() not in ("1", "true", "yes"):
            return
        c = self.client
        if c is None or not isinstance(c.turn_rules, dict):
            return
        cc = c.turn_rules.get("client_contract")
        if not isinstance(cc, dict):
            return
        feats = cc.get("features")
        if not isinstance(feats, list):
            return
        if "retreat_obligations" in feats and c.retreat_obligations is None:
            if not getattr(self, "_warned_missing_retreat_obligations_wire", False):
                self._warned_missing_retreat_obligations_wire = True
                self.logger.warning(
                    "Server turn_rules.client_contract includes 'retreat_obligations' "
                    "but StateUpdate.retreat_obligations is missing for this viewer."
                )

    def _apply_focus_unit_after_state_sync(self, state: GameState) -> None:
        """Apply per-viewer ``StateUpdate.suggested_focus_unit_id`` when valid."""
        client = self.client
        if client is None:
            return
        s = client.suggested_focus_unit_id
        if not isinstance(s, str) or not s.strip():
            return
        uid = s.strip()
        u = state.board.units.get(uid)
        if u is None or not u.active or (client.faction and u.faction != client.faction):
            return
        self.ui_state.select_unit(uid)
        gu = self.board.get_unit(uid)
        if gu is not None:
            self.selection = gu

    def _handle_connection_change(self, state: ConnectionState) -> None:
        self.logger.info(f"Connection state: {state.value}")
        self.connected = state == ConnectionState.CONNECTED

    def _handle_error(self, error: str) -> None:
        self.logger.error(f"Server error: {error}")
        dev_console.set_status(f"Server: {error}")
        self.display_mgr.refresh_unit_positions()

    def _handle_action_result(self, success: bool, error_msg: str | None) -> None:
        if success:
            self.logger.debug("Action accepted by server")
        else:
            self.logger.warning(f"Action rejected: {error_msg}")
            if error_msg:
                dev_console.set_status(f"Server: {error_msg}")
            self.display_mgr.refresh_unit_positions()

    def get_current_state(self) -> GameState:
        """Last replicated game state (authoritative copy mirrors server)."""
        return self.action_mgr.current_state

    def is_my_turn(self) -> bool:
        if not self.client:
            return False
        return self.client.is_my_turn()

    def can_interact_with_unit(self, unit_id: str) -> bool:
        if self.is_my_turn():
            return True
        if not self.client or not self.client.game_state or not self.client.faction:
            return False
        st = self.client.game_state
        u = st.board.units.get(unit_id)
        if u is None or u.faction != self.client.faction:
            return False
        return self.retreat_obligation_hexes_remaining(st, unit_id) is not None

    def retreat_obligation_hexes_remaining(
        self, state: GameState, unit_id: str
    ) -> int | None:
        c = self.client
        if c is not None and isinstance(c.retreat_obligations, dict):
            raw = c.retreat_obligations.get(unit_id)
            if raw is not None:
                try:
                    n = int(raw)
                except (TypeError, ValueError):
                    n = 0
                return n if n > 0 else None
        return None

    def _sync_turn_ui(self, state: GameState) -> None:
        faction = state.turn.current_faction
        phase = state.turn.current_phase
        actions = state.turn.phase_actions_remaining

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

    def advance_turn(self, _) -> None:
        """Send NextPhase derived from replicated schedule (same as server)."""
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
        self.logger.info(f"Advance turn: {np}")
        self._clear_drag_and_highlights()
        self.selection = None
        self.execute_action(np)

    def undo(self) -> None:
        if not self.client or not self.connected:
            self.logger.warning("Cannot undo: not connected to server")
            return

        try:
            self.client.send_undo()
            self.logger.info("Sent undo request to server")
        except Exception as e:
            self.logger.error(f"Failed to send undo request: {e}")

    def redo(self) -> None:
        if not self.client or not self.connected:
            self.logger.warning("Cannot redo: not connected to server")
            return

        try:
            self.client.send_redo()
            self.logger.info("Sent redo request to server")
        except Exception as e:
            self.logger.error(f"Failed to send redo request: {e}")

    def save_snapshot_dict(self) -> dict[str, Any]:
        if not self.client or self.client.game_state is None:
            raise RuntimeError("No game state to save (not connected or no state yet)")
        return {
            "format_version": SNAPSHOT_FORMAT_VERSION,
            "game_state": game_state_to_wire_dict(self.client.game_state),
        }

    def save_snapshot_json(self) -> str:
        return json.dumps(self.save_snapshot_dict(), indent=2)

    def load_snapshot_dict(self, d: dict[str, Any]) -> None:
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
        self.load_snapshot_dict(json.loads(text))

    def _clear_drag_and_highlights(self) -> None:
        """Clear local drag preview, selection, and hex highlights (no server action)."""
        if self.ui_state.drag_preview:
            preview = self.ui_state.end_drag()
            self._restore_drag_preview_to_committed(preview)
        self.ui_state.select_unit(None)
        self.ui_state.select_marker(None)
        mg = getattr(self, "marker_mgr", None)
        if mg is not None:
            mg.set_marker_hilite(None)
        self.display_mgr.clear_highlights()

    def _restore_drag_preview_to_committed(self, preview) -> None:
        """Re-snap unit SVG to its committed hex after a cancelled drag (see mouse maybe_click path)."""
        if preview is None or self.action_mgr is None:
            return
        uid = str(preview.unit_id)
        mg = getattr(self, "marker_mgr", None)
        if (
            mg is not None
            and mg.get_display(uid)
            and self.display_mgr.get_display(uid) is None
        ):
            mg.clear_preview(uid, preview.original_position)
            return
        # Prefer live state; fall back to drag start (preview always has original_position).
        committed_hex = preview.original_position
        st = self.action_mgr.current_state
        u = None
        if st is not None:
            u = st.board.units.get(uid)
            if u is not None:
                committed_hex = u.position
        self.display_mgr.clear_preview(uid, committed_hex)
        # show_preview only changes transform; _hex stays committed. Refresh forces translate.
        self.display_mgr.refresh_unit_positions()

    def start_drag_preview(self, unit_id: str):
        """Start drag preview for a unit."""
        state = self.action_mgr.current_state
        unit_state = state.board.units.get(unit_id)
        if not unit_state:
            return

        self.ui_state.select_unit(unit_id)
        game_unit = self.board.get_unit(unit_id)
        if game_unit:
            self.selection = game_unit

        # Initialize drag preview with unit's current position
        pixel_pos = self.canvas.hex_layout.hex_to_pixel(unit_state.position)
        self.ui_state.start_drag(
            unit_id, unit_state.position, pixel_pos[0], pixel_pos[1]
        )

        # Compute valid moves from committed state
        from ..state.logic import (
            DEFAULT_MOVEMENT_BUDGET,
            compute_retreat_destination_hexes,
            compute_valid_moves,
            retreat_impassable_enemy_zoc_hexes,
        )

        gd = getattr(self, "_title_game_definition", None)
        zoc = None
        if gd is not None:
            zfn = getattr(gd, "zoc_hexes_for_unit", None)
            if callable(zfn):
                zoc = zfn(state, unit_id)
                if zoc is not None and not isinstance(zoc, frozenset):
                    zoc = frozenset(zoc)

        rem = self.retreat_obligation_hexes_remaining(state, unit_id)
        if rem is not None:
            title_zoc = None
            if gd is not None:
                zfn = getattr(gd, "zoc_hexes_for_unit", None)
                if callable(zfn):
                    title_zoc = zfn(state, unit_id)
                    if title_zoc is not None and not isinstance(title_zoc, frozenset):
                        title_zoc = frozenset(title_zoc)
            enemy_only = retreat_impassable_enemy_zoc_hexes(
                state, unit_id, enemy_zoc_ring=title_zoc
            )
            valid_moves = compute_retreat_destination_hexes(
                state,
                unit_id,
                rem,
                float(rem),
                zoc_hexes=None,
                blocked_hexes=enemy_only,
            )
        else:
            move_budget = DEFAULT_MOVEMENT_BUDGET
            if gd is not None:
                fn = getattr(gd, "movement_budget_for_unit", None)
                if callable(fn):
                    move_budget = float(fn(state, unit_id))
            valid_moves = compute_valid_moves(
                state, unit_id, movement_budget=move_budget, zoc_hexes=zoc
            )
        self.ui_state.set_constraints(valid_moves)

        # Clear old highlights and show new ones
        self.display_mgr.clear_highlights()
        self.display_mgr.highlight_hexes(valid_moves)

    def start_drag_preview_marker(self, marker_id: str) -> None:
        """Begin marker drag: highlights valid destination hexes (default: empty board hexes)."""
        from ..state.marker_placement import marker_destination_hexes_for_preview

        mgr = getattr(self, "marker_mgr", None)
        if mgr is None or not mgr.has_display(marker_id):
            return
        state = self.action_mgr.current_state
        if state is None:
            return
        display = mgr.get_display(marker_id)
        if display is None:
            return
        pos_hex = display.position
        self.ui_state.select_unit(None)
        self.ui_state.select_marker(marker_id)
        mgr.set_marker_hilite(marker_id)
        pixel_pos = self.canvas.hex_layout.hex_to_pixel(pos_hex)
        self.ui_state.start_drag(marker_id, pos_hex, pixel_pos[0], pixel_pos[1])
        # Preview uses default empty-hex rule; custom server rules need a client hook later.
        valid = marker_destination_hexes_for_preview(
            state, {"id": marker_id, "type": display.unit_type}, None
        )
        self.ui_state.set_constraints(valid)
        self.display_mgr.clear_highlights()
        self.display_mgr.highlight_hexes(valid)

    def update_drag_preview_marker(
        self, pixel_x: float, pixel_y: float, target_hex
    ) -> None:
        """Same as `update_drag_preview` for an active marker drag."""
        self.update_drag_preview(pixel_x, pixel_y, target_hex)

    def update_drag_preview(self, pixel_x: float, pixel_y: float, target_hex):
        """Update drag preview position."""
        self.ui_state.update_drag(pixel_x, pixel_y, target_hex)

        if self.ui_state.drag_preview:
            # Log the actual zoom/pan values being used
            self.logger.debug(
                f"update_drag_preview: screen=({pixel_x:.1f},{pixel_y:.1f}), "
                f"zoom={self.canvas._zoom_level:.2f}, pan=({self.canvas._pan_x:.1f},{self.canvas._pan_y:.1f})"
            )

            uid = self.ui_state.drag_preview.unit_id
            if self.display_mgr.get_display(uid):
                self.display_mgr.show_preview(
                    unit_id=uid,
                    pixel_x=pixel_x,
                    pixel_y=pixel_y,
                    is_valid=self.ui_state.drag_preview.is_valid,
                )
            else:
                mgr = getattr(self, "marker_mgr", None)
                if mgr and mgr.get_display(uid):
                    mgr.show_preview(
                        uid,
                        pixel_x,
                        pixel_y,
                        self.ui_state.drag_preview.is_valid,
                    )

    def end_drag_preview(self) -> bool:
        """
        End drag preview and commit if valid.
        Returns True if move was committed, False otherwise.
        """
        preview = self.ui_state.end_drag()

        if not preview:
            return False

        uid = str(preview.unit_id)
        mgr = getattr(self, "marker_mgr", None)
        is_marker = (
            mgr is not None
            and mgr.get_display(uid) is not None
            and self.display_mgr.get_display(uid) is None
        )

        # Current hex is in movement_constraints (cost 0), so same-hex drags look
        # "valid" but must not commit: state would not change and _update_unit_display
        # would skip re-applying the transform, leaving the unit stuck at preview coords.
        will_commit = (
            preview.is_valid
            and preview.potential_target is not None
            and preview.potential_target != preview.original_position
        )

        if not will_commit:
            self._restore_drag_preview_to_committed(preview)

        self.display_mgr.clear_highlights()

        if will_commit:
            if is_marker:
                from ..state.actions import MoveMarker

                self.execute_action(
                    MoveMarker(
                        marker_id=uid,
                        from_hex=preview.original_position,
                        to_hex=preview.potential_target,
                    )
                )
            else:
                from ..state.actions import MoveUnit

                action = MoveUnit(
                    unit_id=preview.unit_id,
                    from_hex=preview.original_position,
                    to_hex=preview.potential_target,
                )
                self.execute_action(action)
            self.ui_state.select_marker(None)
            if mgr is not None:
                mgr.set_marker_hilite(None)
            return True

        self.ui_state.select_marker(None)
        if mgr is not None:
            mgr.set_marker_hilite(None)
        return False
