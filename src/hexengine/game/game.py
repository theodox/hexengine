from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .arcs.client_title_load import ClientTitleLoadConnectState

from .. import dev_console
from ..client import DisplayManager, LocalServerManager, UIState
from ..client.marker_manager import MarkerManager
from ..client.websocket_client import BrowserWebSocketClient, ConnectionState
from ..document import create_proxy, element, js
from ..gamedef.builtin import (
    InterleavedTwoFactionGameDefinition,
    StaticScheduleGameDefinition,
)
from ..gamedef.client_title_data import ClientTitleData
from ..gamedef.protocol import GameDefinition
from ..hexes.types import Hex
from ..map import Map
from ..state import ActionManager, DEFAULT_MOVEMENT_BUDGET, GameState
from ..state.snapshot import SNAPSHOT_FORMAT_VERSION, game_state_to_wire_dict
from ..ui import MapOverlayManager, PopupManager
from ..ui.dom import apply_css_classes
from .arcs.client_combat import ClientCombatMixin
from .arcs.client_interaction_panels import ClientInteractionPanelsMixin
from .arcs.client_place_marker import ClientPlaceMarkerMixin
from .arcs.client_retreat_path import ClientRetreatPathMixin
from .board import GameBoard
from .events import Hotkey, HotkeyHandlerMixin, Modifiers, MouseEventHandlerMixin
from .history import GameHistoryMixin

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
        budget = float(wire.get("movement_budget", DEFAULT_MOVEMENT_BUDGET))
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
    budget = float(wire.get("movement_budget", DEFAULT_MOVEMENT_BUDGET))
    return InterleavedTwoFactionGameDefinition(
        factions=factions, movement_budget=budget, **per_kw
    )


class Game(
    MouseEventHandlerMixin,
    HotkeyHandlerMixin,
    GameHistoryMixin,
    ClientPlaceMarkerMixin,
    ClientRetreatPathMixin,
    ClientCombatMixin,
    ClientInteractionPanelsMixin,
):
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
    ) -> None:
        self.running = True
        container = element("map-container")
        map = element("map-canvas")
        terrain = element("map-terrain")
        svg = element("map-svg")
        markers = element("map-markers")
        units = element("map-units")
        self.popup_manager = PopupManager(container)

        assert map is not None, "Map canvas element not found"
        assert svg is not None, "Map SVG element not found"
        self.canvas = Map(container, map, terrain, svg, markers, units)
        self.map_overlay_manager = MapOverlayManager(self.canvas)
        self.board = GameBoard(self.canvas)

        # Placeholder state before the first authoritative StateUpdate arrives.
        # Do not assume title-specific faction/phase ids here.
        initial_state = GameState.create_empty()
        self.action_mgr = ActionManager(initial_state)
        self.logger = logging.getLogger("game")
        self.logger.info(f"action_mgr created: {self.action_mgr}")
        self._engine_banner_message: dict[str, Any] | None = None
        self._last_faction_display_contract_error: str | None = None
        self._title_load_splash_dismissed: bool = False

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
        # Attack planning (optional; see ClientCombatMixin + attack_planning_ui feature)
        self.attack_plan_target_hex = None
        self.attack_plan_attacker_ids: set[str] = set()
        self._attack_plan_suppress_bg_mouseup_retarget = False
        self._attack_plan_target_overlay = None
        self._attack_plan_los_svg_group = None
        self._attack_plan_los_lines = {}
        self._map_selection_preview = None
        self._map_selection_preview_request_id = ""
        self._map_selection_preview_pending = False
        self.retreat_path_unit_id = None
        self.retreat_path_hexes = []
        self.retreat_path_committed = None
        self.retreat_path_continue_index = 0
        self.place_marker_id = None
        self.place_marker_from_hex = None
        self.place_marker_to_hex = None
        # Mirror INFORM ``ui_popup`` copy on ``#status-line`` when dev console is up.
        self.repeat_ui_popup_to_dev_console = True
        self._retreat_path_svg_group = None
        self._retreat_path_polyline_el = None
        self._interaction_panel_roots: dict[str, Any] = {}
        self._interaction_panel_action_buttons: dict[str, dict[str, Any]] = {}
        self._interaction_panel_input_elements: dict[str, dict[str, Any]] = {}
        self._interaction_panel_wire_specs: dict[str, dict[str, Any]] = {}
        from .arcs.client_interaction_panels import _remove_legacy_advance_button

        _remove_legacy_advance_button()

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

        self.server_url = server_url
        self.player_name = player_name
        self.preferred_faction = preferred_faction
        self.use_local_server = use_local_server
        self.client: BrowserWebSocketClient | None = None
        self.local_server: LocalServerManager | None = None
        self._title_game_definition: GameDefinition | None = None
        self._local_game_definition: GameDefinition | None = None
        self._unit_preview_request_id: str = ""
        self._marker_preview_request_id: str = ""
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

    def _interactive_game_state(self) -> GameState | None:
        """Committed state for UI/interaction: prefer live server snapshot when connected."""
        client = getattr(self, "client", None)
        if (
            client is not None
            and client.is_connected()
            and client.game_state is not None
        ):
            return client.game_state
        if self.action_mgr is not None:
            return self.action_mgr.current_state
        return None

    def _client_title_data(self) -> ClientTitleData:
        """Parsed `GameData` subset from the last `StateUpdate.turn_rules` (if any)."""
        c = getattr(self, "client", None)
        return ClientTitleData.from_turn_rules(c.turn_rules if c is not None else None)

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
            if self.client:
                self.client.send_inspect("unit", str(self.selection.unit_id))
            self.logger.info(f"Inspect unit {self.selection.unit_id}")
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

    @Hotkey("h", Modifiers.ALT)
    def toggle_hex_address_labels(self) -> None:
        """Toggle odd-q col,row labels on each map hex (same as TOML [col, row])."""
        on = self.canvas.toggle_hex_address_labels()
        self.logger.info("Hex address labels %s (Alt+H)", "on" if on else "off")

    # ===== SERVER SESSION (WebSocket) =====

    # --- Client title-load arc (see game.arcs.client_title_load) ---

    def title_load_reset_for_connect(self) -> None:
        if self.client is not None:
            self.client.disconnect()
            self.client = None
        self._title_game_definition = None
        self._title_load_splash_dismissed = False

    def title_load_resolve_scenario(self) -> Path | None:
        from ..gameroot import resolve_scenario_path_with_game_root

        try:
            return Path(resolve_scenario_path_with_game_root()).resolve()
        except (FileNotFoundError, ValueError, OSError):
            return None

    def title_load_invoke_splash_hook(self, scenario_path: Path) -> None:
        from ..gameroot import run_title_load_splash

        run_title_load_splash(scenario_path)

    def title_load_invoke_setup_hook(self, scenario_path: Path) -> bool:
        from ..gameroot import run_title_load_setup

        return run_title_load_setup(scenario_path)

    def title_load_boot_local_server(
        self, scenario_path: Path, state: ClientTitleLoadConnectState
    ) -> bool:
        from ..gameroot import (
            initial_turn_slot_for_game_definition,
            load_game_definition_for_scenario,
        )
        from ..scenarios import load_scenario
        from ..scenarios.loader import scenario_to_initial_state

        self.logger.info("Starting local server...")
        scenario_data = load_scenario(scenario_path)
        game_def = load_game_definition_for_scenario(scenario_path)
        self._local_game_definition = game_def
        first = initial_turn_slot_for_game_definition(game_def)
        state.preloaded_unit_graphics = scenario_data.unit_graphics_to_wire_dict()
        state.preloaded_marker_graphics = getattr(
            scenario_data, "marker_graphics_to_wire_dict", lambda: {}
        )()
        state.preloaded_markers = getattr(
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
            unit_graphics=state.preloaded_unit_graphics,
            marker_graphics=state.preloaded_marker_graphics,
            markers=state.preloaded_markers,
            game_definition=game_def,
        )
        if not self.local_server.start():
            self.logger.error("Failed to start local server")
            return False
        return True

    def title_load_prepare_websocket_client(
        self, state: ClientTitleLoadConnectState
    ) -> None:
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
        self.client.on_ui_popup = self._handle_ui_popup
        self.client.on_marker_preview = self._handle_marker_preview
        self.client.on_unit_preview = self._handle_unit_preview
        self.client.on_map_selection_preview = self._handle_map_selection_preview

    def title_load_begin_websocket_connect(
        self, state: ClientTitleLoadConnectState
    ) -> None:
        if self.client is None:
            raise RuntimeError("WebSocket client not prepared")
        if state.preloaded_unit_graphics is not None:
            self.display_mgr.apply_unit_graphics(state.preloaded_unit_graphics)
            self.client._applied_unit_graphics_json = json.dumps(
                state.preloaded_unit_graphics, sort_keys=True, ensure_ascii=True
            )
        if state.preloaded_marker_graphics is not None:
            self.marker_mgr.apply_marker_graphics(state.preloaded_marker_graphics)
            self.client._applied_marker_graphics_json = json.dumps(
                state.preloaded_marker_graphics, sort_keys=True, ensure_ascii=True
            )
        if state.preloaded_markers is not None:
            self.marker_mgr.sync_markers(state.preloaded_markers)
        self.client.connect(
            player_name=self.player_name, preferred_faction=self.preferred_faction
        )
        self.logger.info("Connection initiated...")

    def title_load_on_connect_failed(self) -> None:
        from .title_load_ui import force_hide_splash

        force_hide_splash()

    @property
    def title_load_splash_dismissed(self) -> bool:
        return self._title_load_splash_dismissed

    def title_load_mark_splash_dismissed(self) -> None:
        self._title_load_splash_dismissed = True

    def connect(self) -> bool:
        """
        Connect to the game server.

        Reconnecting the same client to the same match is supported; switching to a
        different title/scenario is assumed rare (full reload / prepared restart).

        Runs the client title-load arc (splash/setup hooks, local server, WebSocket).
        """
        from .arcs.client_title_load import execute_client_title_load_connect_arc

        try:
            return execute_client_title_load_connect_arc(self)
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self.title_load_on_connect_failed()
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
        self._local_game_definition = None
        self.connected = False
        from .title_load_ui import force_hide_splash

        force_hide_splash()
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
        self.execute_action_request(action_type, params)

    def execute_action_request(self, action_type: str, params: dict[str, Any]) -> None:
        """Send an already-serialized action request to the server."""
        if str(action_type).strip() == "AttackPlanCancel":
            self.cancel_attack_plan()
            return
        if not self.client or not self.connected:
            self.logger.warning("Cannot execute action: not connected to server")
            return
        try:
            self.client.send_action(str(action_type), dict(params))
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

    def _title_state_extension_key(self) -> str | None:
        """Pack bucket in GameState.extension for combat/retreat (server turn_rules)."""
        td = self._client_title_data()
        if td.title_state_extension_key:
            return td.title_state_extension_key
        gd = getattr(self, "_title_game_definition", None)
        if gd is not None:
            try:
                gk = gd.game_data.title_state_extension_key
            except AttributeError:
                gk = None
            if isinstance(gk, str) and gk.strip():
                return gk.strip()
        return None

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

        self._sync_map_overlays()
        self._sync_faction_display_contract_banner()
        self._sync_interaction_messages()
        self._sync_interaction_panels()
        self._apply_title_faction_css()
        from .arcs.client_title_load import execute_client_title_load_ready_segment

        execute_client_title_load_ready_segment(self)
        self._apply_focus_unit_after_state_sync(new_state)
        self._sync_attack_plan_after_state_update()
        self._sync_retreat_path_after_state_update(new_state)
        self._maybe_continue_retreat_path()

    def _sync_retreat_path_after_state_update(self, new_state) -> None:
        if not self._client_has_retreat_path_selection():
            if getattr(self, "retreat_path_unit_id", None):
                self.cancel_retreat_path()
            return

        active_uid = getattr(self, "retreat_path_unit_id", None)
        if isinstance(active_uid, str) and active_uid.strip():
            local = [h for h in self.retreat_path_hexes if isinstance(h, Hex)]
            if len(local) >= 2:
                self._sync_retreat_path_polyline(local)
            # Keep an extended draft across state sync churn.
            if len(local) > 1 or self._retreat_path_active():
                return

        uid = self.ui_state.selected_unit_id
        if uid is None:
            return
        uid_s = str(uid).strip()
        if self.retreat_obligation_hexes_remaining(new_state, uid_s) is None:
            if getattr(self, "retreat_path_committed", None) is None:
                self.cancel_retreat_path()
            return
        if getattr(self, "retreat_path_unit_id", None) != uid_s:
            local_len = len(
                [h for h in getattr(self, "retreat_path_hexes", []) if isinstance(h, Hex)]
            )
            if local_len <= 1:
                self.begin_retreat_path_for_unit(uid_s)

    def _sync_interaction_messages(self) -> None:
        """Render per-recipient `StateUpdate.interaction_messages` as a small banner."""
        from ..document import element, js, jsnull, wire_str

        client = self.client
        msgs = client.interaction_messages if client is not None else None
        rows = (
            [m for m in msgs if isinstance(m, dict)] if isinstance(msgs, list) else []
        )
        if self._engine_banner_message is not None:
            rows = [*rows, dict(self._engine_banner_message)]
        if rows:
            now_ms = int(js.Date.now())
            kept: list[dict[str, Any]] = []
            for r in rows:
                ttl = r.get("ttl_ms")
                recv = r.get("_received_at_ms")
                if isinstance(ttl, int) and ttl >= 0 and isinstance(recv, int):
                    if now_ms - recv > ttl:
                        continue
                kept.append(r)
            # Dedupe by key (last one wins).
            deduped: dict[str, dict[str, Any]] = {}
            passthrough: list[dict[str, Any]] = []
            for r in kept:
                dk = r.get("dedupe_key")
                if isinstance(dk, str) and dk:
                    deduped[dk] = r
                else:
                    passthrough.append(r)
            rows = [*passthrough, *deduped.values()]

        def paint_interaction_banner(
            text: str,
            html: str,
            base: str,
            extra_cls: str = "",
            fac: str | None = None,
        ) -> None:
            if fac is None:
                st = self.action_mgr.current_state
                fac = wire_str(st.turn.current_faction) if st is not None else ""
            _, faction_cls = self._faction_ui_for(fac)
            banner_el = js.document.getElementById("interaction-banner")
            if banner_el is None or banner_el is jsnull:
                ui = element("ui-panel")
                banner_el = js.document.createElement("div")
                banner_el.id = "interaction-banner"
                ui.appendChild(banner_el)
            if html:
                banner_el.innerHTML = html
            else:
                banner_el.innerText = text
            banner_el.className = " ".join(
                c for c in (base, extra_cls, faction_cls or "") if c
            ).strip()

        def clear_interaction_banner() -> None:
            el = js.document.getElementById("interaction-banner")
            if el is not None and el is not jsnull:
                el.innerText = ""
                el.innerHTML = ""
                el.className = ""

        if not rows:
            # Prefer replicated turn state when there are no server messages (e.g. all TTL-expired
            # rows from an older server build, or empty interaction_messages).
            st_fb = self.action_mgr.current_state
            if st_fb is not None and client is not None:
                t = st_fb.turn
                text_fb = (
                    f"{wire_str(t.current_faction)}: {wire_str(t.current_phase)} "
                    f"(actions: {t.phase_actions_remaining})"
                )
                paint_interaction_banner(text_fb, "", "interaction-msg--phase")
                return
            clear_interaction_banner()
            return

        def _prio(kind: str) -> int:
            return {
                "error": 40,
                "retreat": 30,
                "advance": 25,
                "wait": 20,
                "phase": 10,
                "info": 5,
            }.get(kind, 0)

        best: dict[str, Any] | None = None
        best_p = -1
        for r in rows:
            t = wire_str(r.get("text")).strip()
            h = wire_str(r.get("html")).strip()
            if not t and not h:
                continue
            kraw = r.get("kind")
            k = wire_str(kraw).strip()
            p = _prio(k)
            if p >= best_p:
                best_p = p
                best = r
        if best is None:
            st_fb = self.action_mgr.current_state
            if st_fb is not None and client is not None:
                t = st_fb.turn
                text_fb = (
                    f"{wire_str(t.current_faction)}: {wire_str(t.current_phase)} "
                    f"(actions: {t.phase_actions_remaining})"
                )
                paint_interaction_banner(text_fb, "", "interaction-msg--phase")
            return
        text = wire_str(best.get("text")).strip()
        html = wire_str(best.get("html")).strip()
        kind = wire_str(best.get("kind")).strip()
        extra_cls = wire_str(best.get("css_class")).strip()
        if not extra_cls:
            extra_cls = self._client_title_data().css_class_for_interaction_kind(kind)

        base = (
            "interaction-msg--retreat"
            if kind == "retreat"
            else "interaction-msg--advance"
            if kind == "advance"
            else "interaction-msg--wait"
            if kind == "wait"
            else "interaction-msg--phase"
            if kind == "phase"
            else ""
        )
        fac = ""
        st = self.action_mgr.current_state
        if st is not None:
            fac = wire_str(st.turn.current_faction)
        paint_interaction_banner(text, html, base, extra_cls, fac)

    def _set_engine_banner_message(
        self,
        *,
        kind: str,
        text: str,
        ttl_ms: int | None,
        css_class: str | None = None,
        dedupe_key: str = "engine",
    ) -> None:
        """Local-only banner message for engine/runtime failures (not title-controlled)."""
        from ..document import create_proxy, js

        now_ms = int(js.Date.now())
        self._engine_banner_message = {
            "schema": 1,
            "kind": str(kind),
            "text": str(text),
            "dedupe_key": str(dedupe_key).strip() or "engine",
            "ttl_ms": ttl_ms,
            "css_class": str(css_class).strip()
            if isinstance(css_class, str) and css_class.strip()
            else None,
            "_received_at_ms": now_ms,
        }
        # If this message has a TTL, schedule a re-sync so it can disappear without
        # waiting for the next server StateUpdate.
        if isinstance(ttl_ms, int) and ttl_ms >= 0:
            js.setTimeout(
                create_proxy(lambda: self._sync_interaction_messages()), ttl_ms + 50
            )

    def _sync_faction_display_contract_banner(self) -> None:
        """Surface faction label contract violations from turn_rules (local banner)."""
        if self.client is None:
            return
        td = self._client_title_data()
        err = td.faction_display_contract_error
        if err == self._last_faction_display_contract_error:
            return
        self._last_faction_display_contract_error = err
        if err:
            self._set_engine_banner_message(
                kind="error",
                text=err,
                ttl_ms=None,
                css_class="interaction-msg--error",
                dedupe_key="faction_display_contract",
            )
        else:
            msg = self._engine_banner_message
            if (
                isinstance(msg, dict)
                and msg.get("dedupe_key") == "faction_display_contract"
            ):
                self._engine_banner_message = None

    def _faction_ui_for(self, faction_id: str) -> tuple[str, str | None]:
        """Resolve (label, css_class) for faction_id from server turn_rules."""
        td = self._client_title_data()
        if td.faction_display_contract_error:
            return str(faction_id), None
        fu = td.faction_ui
        if fu is not None:
            row = fu.row_for(faction_id)
            if row is not None:
                if row.label is not None:
                    return row.label, row.css_class
                return str(faction_id), row.css_class
        return str(faction_id), None

    def _apply_title_faction_css(self) -> None:
        """Inject optional title CSS from turn_rules.faction_ui (inline + href)."""
        from ..document import js, jsnull

        css: str | None = None
        css_href: str | None = None
        fu = self._client_title_data().faction_ui
        if fu is not None:
            css = fu.css_inline
            css_href = fu.css_href
        css_norm = css.strip() if isinstance(css, str) else ""
        if getattr(self, "_applied_title_css", None) == css_norm and getattr(
            self, "_applied_title_css_href", None
        ) == (css_href or ""):
            return
        self._applied_title_css = css_norm
        self._applied_title_css_href = css_href or ""

        doc = js.document
        parent = doc.body if doc.body else doc.head

        # Link-based sheet (preferred for title resources).
        link_id = "hexengine-styles-title-link"
        link_el = doc.getElementById(link_id)
        if not css_href:
            if link_el is not None and link_el is not jsnull:
                parent = link_el.parentNode
                if parent is not None and parent is not jsnull:
                    parent.removeChild(link_el)
        else:
            if link_el is None or link_el is jsnull:
                link_el = doc.createElement("link")
                link_el.id = link_id
                link_el.rel = "stylesheet"
                parent.appendChild(link_el)
            link_el.href = css_href

        style_id = "hexengine-styles-title-inline"
        el = doc.getElementById(style_id)
        if el is None or el is jsnull:
            if not css_norm:
                return
            style_el = doc.createElement("style")
            style_el.id = style_id
            style_el.innerHTML = css_norm
            parent.appendChild(style_el)
            return
        if not css_norm:
            parent = el.parentNode
            if parent is not None and parent is not jsnull:
                parent.removeChild(el)
            return
        el.innerHTML = css_norm

    def _maybe_warn_missing_title_sync(self) -> None:
        """
        Dev guardrail: warn when the server advertises a contract feature but the
        corresponding per-update field is missing.
        """
        import os

        if os.getenv("HEXENGINE_STRICT_TITLE_SYNC", "").strip() not in (
            "1",
            "true",
            "yes",
        ):
            return
        c = self.client
        if c is None:
            return
        td = self._client_title_data()
        if (
            "retreat_obligations" in td.client_contract_features
            and c.retreat_obligations is None
        ):
            if not getattr(self, "_warned_missing_retreat_obligations_wire", False):
                self._warned_missing_retreat_obligations_wire = True
                self.logger.warning(
                    "Server turn_rules.client_contract includes 'retreat_obligations' "
                    "but StateUpdate.retreat_obligations is missing for this viewer."
                )

    def _apply_focus_unit_after_state_sync(self, state: GameState) -> None:
        """Apply per-viewer StateUpdate.suggested_focus_unit_id when valid."""
        client = self.client
        if client is None:
            return
        s = client.suggested_focus_unit_id
        if not isinstance(s, str) or not s.strip():
            return
        uid = s.strip()
        u = state.board.units.get(uid)
        if (
            u is None
            or not u.active
            or (client.faction and u.faction != client.faction)
        ):
            return
        self.ui_state.select_unit(uid)
        gu = self.board.get_unit(uid)
        if gu is not None:
            self.selection = gu

    def _handle_connection_change(self, state: ConnectionState) -> None:
        self.logger.info(f"Connection state: {state.value}")
        self.connected = state == ConnectionState.CONNECTED
        if state in (ConnectionState.DISCONNECTED, ConnectionState.FAILED):
            self._set_engine_banner_message(
                kind="error",
                text=f"Disconnected: {state.value}",
                ttl_ms=None,
                css_class="interaction-msg--error",
            )
            self._sync_interaction_messages()
        elif state == ConnectionState.RECONNECTING:
            self._set_engine_banner_message(
                kind="info",
                text="Reconnecting…",
                ttl_ms=None,
                css_class="interaction-msg--info",
            )
            self._sync_interaction_messages()
        elif state == ConnectionState.CONNECTED:
            self._engine_banner_message = None

    def _handle_error(self, error: str) -> None:
        self.logger.error(f"Server error: {error}")
        dev_console.set_status(f"Server: {error}")
        self._set_engine_banner_message(
            kind="error",
            text=f"Server: {error}",
            ttl_ms=6_000,
            css_class="interaction-msg--error",
        )
        self._sync_interaction_messages()
        # Re-snap visuals to committed state (e.g. rejected move left preview transform).
        st = self._interactive_game_state()
        if st is not None:
            self.display_mgr.sync_from_state(st)
        else:
            self.display_mgr.refresh_unit_positions()

    def _handle_action_result(self, success: bool, error_msg: str | None) -> None:
        if success:
            self.logger.debug("Action accepted by server")
        else:
            self.logger.warning(f"Action rejected: {error_msg}")
            if error_msg:
                dev_console.set_status(f"Server: {error_msg}")
                self._set_engine_banner_message(
                    kind="error",
                    text=str(error_msg),
                    ttl_ms=5_000,
                    css_class="interaction-msg--error",
                )
                self._sync_interaction_messages()
            self.display_mgr.refresh_unit_positions()

    def show_inform_popup(
        self,
        inform_kind: str,
        reason: str,
        *,
        hex: Hex | None = None,
        unit_id: str | None = None,
    ) -> None:
        """
        INFORM lane: server title hook formats copy; client renders ``ui_popup``.

        Replaces direct ``popup_manager.create_popup`` for title-authored feedback.
        """
        client = self.client
        if client is None or not client.is_connected():
            return
        hex_wire: dict[str, int] | None = None
        if isinstance(hex, Hex):
            hex_wire = {"i": int(hex.i), "j": int(hex.j), "k": int(hex.k)}
        client.send_inform_popup(
            inform_kind,
            reason,
            hex_wire=hex_wire,
            unit_id=unit_id,
        )

    def _handle_ui_popup(self, payload: dict[str, Any]) -> None:
        """
        Title-formatted informational popup (INFORM / ``ui_popup`` wire).

        Used for unit/marker inspect and ``inform`` map callouts from the server.
        """
        if not isinstance(payload, dict):
            return
        raw_html = payload.get("html")
        raw_text = payload.get("text")
        html = "" if raw_html is None else str(raw_html).strip()
        text = "" if raw_text is None else str(raw_text).strip()
        if not html and not text:
            return
        hx = payload.get("hex")
        if not isinstance(hx, dict):
            return
        try:
            i = int(hx.get("i"))
            j = int(hx.get("j"))
            k = int(hx.get("k"))
        except Exception:
            return
        from ..hexes.types import Hex

        mx, my = self.layout.hex_to_pixel(Hex(i, j, k))
        pos = self.canvas.map_space_to_container_pixel(mx, my)
        ttl_ms: int | None = None
        raw_ttl = payload.get("ttl_ms")
        if raw_ttl is not None:
            try:
                ttl_ms = max(0, int(raw_ttl))
            except (TypeError, ValueError):
                ttl_ms = None
        raw_class = payload.get("css_class")
        css_class = (
            str(raw_class).strip()
            if isinstance(raw_class, str) and str(raw_class).strip()
            else None
        )
        popup_kw = {
            "timeout_ms": ttl_ms,
            "css_class": css_class,
            "auto_dismiss": ttl_ms is not None,
        }
        if html:
            self.popup_manager.create_popup_html(html, pos, **popup_kw)
        else:
            self.popup_manager.create_popup(text, pos, **popup_kw)
        if getattr(self, "repeat_ui_popup_to_dev_console", False):
            dev_console.repeat_ui_popup_to_status(payload)

    def _sync_map_overlays(self) -> None:
        """Apply StateUpdate.map_overlays via MapOverlayManager."""
        client = self.client
        rows = client.map_overlays if client is not None else []
        self.map_overlay_manager.sync(rows)

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

    def _max_active_units_per_hex(self) -> int | None:
        """Optional stacking limit from server turn_rules (title-owned)."""
        return self._client_title_data().max_active_units_per_hex

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

    def _clear_drag_and_highlights(self, *, keep_secondary: bool = False) -> None:
        """Clear local drag preview, selection, and hex highlights (no server action).

        Args:
            keep_secondary: When True, preserves secondary selection highlights (multi-select).
        """
        self._unit_preview_request_id = ""
        self._marker_preview_request_id = ""
        if self.ui_state.drag_preview:
            preview = self.ui_state.end_drag()
            self._restore_drag_preview_to_committed(preview)
        self.ui_state.select_unit(None, exclusive=not keep_secondary)
        self.ui_state.select_marker(None, exclusive=not keep_secondary)
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
        state = self._interactive_game_state()
        if state is None:
            return
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
        # Ask authoritative server for destination preview hexes so thin clients match.
        if self.client is not None:
            self.client.send_unit_preview_request(unit_id)
            # The websocket client increments its own counter; capture the latest id.
            self._unit_preview_request_id = str(
                getattr(self.client, "_preview_req_counter", "")
            )
        self.ui_state.set_constraints(set())
        self.display_mgr.clear_highlights()

    def _handle_unit_preview(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return
        uid = payload.get("unit_id")
        if not isinstance(uid, str) or not uid.strip():
            return
        if self.ui_state.drag_preview is None:
            return
        if str(self.ui_state.drag_preview.unit_id) != uid:
            return
        rid = payload.get("request_id")
        if (
            isinstance(rid, str)
            and self._unit_preview_request_id
            and rid != self._unit_preview_request_id
        ):
            return

        rows = payload.get("hexes")
        if not isinstance(rows, list):
            return
        from ..hexes.types import Hex

        valid: set[Hex] = set()
        for r in rows:
            if not isinstance(r, dict):
                continue
            try:
                valid.add(Hex(int(r["i"]), int(r["j"]), int(r["k"])))
            except Exception:
                continue
        # Endpoints are the only valid drop targets.
        self.ui_state.set_constraints(valid)

        cls = "highlight"
        raw_cc = payload.get("css_class")
        if isinstance(raw_cc, str) and raw_cc.strip():
            cls = raw_cc.strip()
        else:
            hi = self._client_title_data().hex_highlights
            kind = str(payload.get("kind", "")).strip()
            if kind == "retreat":
                raw = hi.retreat_hex_class
            else:
                raw = hi.move_hex_class
            if isinstance(raw, str) and raw.strip():
                cls = raw.strip()

        self.display_mgr.clear_highlights()
        # Retreat preview can include "through" hexes that are reachable but not endpoints.
        kind = str(payload.get("kind", "")).strip()
        if kind == "retreat":
            through_rows = payload.get("through_hexes")
            through_cls = payload.get("through_css_class")
            through: set[Hex] = set()
            if isinstance(through_rows, list):
                for r in through_rows:
                    if not isinstance(r, dict):
                        continue
                    try:
                        through.add(Hex(int(r["i"]), int(r["j"]), int(r["k"])))
                    except Exception:
                        continue
            if through:
                tcls = (
                    str(through_cls).strip()
                    if isinstance(through_cls, str) and through_cls.strip()
                    else cls
                )
                self.display_mgr.highlight_hexes(through, cls=tcls)
        self.display_mgr.highlight_hexes(valid, cls=cls)

    def start_drag_preview_marker(self, marker_id: str) -> None:
        """Begin marker drag: highlights valid destination hexes (default: empty board hexes)."""
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
        # Ask authoritative server for destination preview hexes so thin clients match.
        if self.client is not None:
            self.client.send_marker_preview_request(marker_id, display.unit_type)
            self._marker_preview_request_id = str(
                getattr(self.client, "_preview_req_counter", "")
            )
        valid: set[Any] = set()
        self.ui_state.set_constraints(valid)
        cls = "highlight"
        raw_m = self._client_title_data().hex_highlights.marker_hex_class
        if isinstance(raw_m, str) and raw_m.strip():
            cls = raw_m.strip()
        self.display_mgr.clear_highlights()
        self.display_mgr.highlight_hexes(set(), cls=cls)

    def _handle_marker_preview(self, payload: dict[str, Any]) -> None:
        """Apply server-provided marker destination preview to the current drag."""
        if not isinstance(payload, dict):
            return
        mid = payload.get("marker_id")
        if not isinstance(mid, str) or not mid.strip():
            return
        if self.ui_state.drag_preview is None:
            return
        if str(self.ui_state.drag_preview.unit_id) != mid:
            return
        rid = payload.get("request_id")
        if (
            isinstance(rid, str)
            and self._marker_preview_request_id
            and rid != self._marker_preview_request_id
        ):
            return
        rows = payload.get("hexes")
        if not isinstance(rows, list):
            return
        from ..hexes.types import Hex

        valid: set[Hex] = set()
        for r in rows:
            if not isinstance(r, dict):
                continue
            try:
                valid.add(Hex(int(r["i"]), int(r["j"]), int(r["k"])))
            except Exception:
                continue
        self.ui_state.set_constraints(valid)
        cls = "highlight"
        raw_cc = payload.get("css_class")
        if isinstance(raw_cc, str) and raw_cc.strip():
            cls = raw_cc.strip()
        else:
            raw_m = self._client_title_data().hex_highlights.marker_hex_class
            if isinstance(raw_m, str) and raw_m.strip():
                cls = raw_m.strip()
        self.display_mgr.clear_highlights()
        self.display_mgr.highlight_hexes(valid, cls=cls)

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
        # Invalidate any in-flight preview responses for the prior drag.
        self._unit_preview_request_id = ""
        self._marker_preview_request_id = ""

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
