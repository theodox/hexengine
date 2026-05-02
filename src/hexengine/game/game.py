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
    StaticScheduleGameDefinition,
)
from ..gamedef.protocol import GameDefinition
from ..map import Map
from ..state import ActionManager, GameState
from ..state.snapshot import SNAPSHOT_FORMAT_VERSION, game_state_to_wire_dict
from ..ui import MapOverlayManager, PopupManager
from .board import GameBoard
from .events import Hotkey, HotkeyHandlerMixin, Modifiers, MouseEventHandlerMixin
from .history import GameHistoryMixin
from .turn_strip import display_faction_name

# Screen-space pan per arrow key when zoomed in; Shift multiplies step.
_PAN_KEY_STEP = 48
_PAN_KEY_SHIFT_MULT = 3


def _phase_allows_attack_planning(phase: str | None) -> bool:
    """True when the committed turn phase should allow declaring attacks (client UX)."""
    p = str(phase or "").strip().lower()
    return p in ("combat", "attack")


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
    budget = float(wire.get("movement_budget", 4.0))
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
        self.map_overlay_manager = MapOverlayManager(self.canvas)
        self.board = GameBoard(self.canvas)

        # Placeholder state before the first authoritative StateUpdate arrives.
        # Do not assume title-specific faction/phase ids here.
        initial_state = GameState.create_empty()
        self.action_mgr = ActionManager(initial_state)
        self.logger = logging.getLogger("game")
        self.logger.info(f"action_mgr created: {self.action_mgr}")
        self._engine_banner_message: dict[str, Any] | None = None

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
        # --- Attack planning UX (client-side, no server sync) ---
        self.attack_plan_target_hex: "Hex | None" = None
        self.attack_plan_attacker_ids: set[str] = set()
        #: True after combat-phase attack-plan unit mousedown (enemy target pick or friendly
        #: attacker toggle); suppresses bogus ``mouseup`` on map background retargeting.
        self._attack_plan_suppress_bg_mouseup_retarget: bool = False
        self._attack_plan_target_overlay = None
        self._attack_plan_los_svg_group = None
        self._attack_plan_los_lines: dict[str, Any] = {}
        self._attack_controls_root = None
        self._attack_controls_status = None
        self._attack_controls_confirm = None
        self._attack_controls_cancel = None
        self._init_attack_controls(element("advance"))

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

    def _sync_attack_plan_after_state_update(self) -> None:
        """Keep attack planning UI in sync with server state (clears stale overlays)."""
        if self.attack_plan_target_hex is None and not self.attack_plan_attacker_ids:
            self._sync_attack_plan_ui()
            return
        st = self._interactive_game_state()
        if st is None:
            self.cancel_attack_plan()
            return
        phase_ok = _phase_allows_attack_planning(getattr(st.turn, "current_phase", None))
        my_turn = True
        client = getattr(self, "client", None)
        if client is not None and client.is_connected() and client.faction:
            my_turn = self.is_my_turn()
        if not phase_ok or not my_turn:
            self.cancel_attack_plan()
            return
        tgt = self.attack_plan_target_hex
        if tgt is not None and not self._attack_target_hex_has_enemy(st, tgt):
            self.cancel_attack_plan()
            return
        self._sync_attack_plan_ui()

    def _init_attack_controls(self, primary_actions_host) -> None:
        """
        Create Confirm/Cancel UI for the attack planning flow.

        Host is the same permanent shell as the advance-turn control (``#advance``),
        outside ``#map-container``, so map mouse handlers never treat button clicks
        as hex picks.
        """
        try:
            root = js.document.createElement("div")
            root.className = "hexengine-attack-controls"

            status = js.document.createElement("div")
            status.className = "hexengine-attack-controls__status"
            status.textContent = "Combat: pick a target hex."
            root.appendChild(status)

            row = js.document.createElement("div")
            row.className = "hexengine-attack-controls__row"

            btn_cancel = js.document.createElement("button")
            btn_cancel.className = "hexengine-attack-controls__cancel"
            btn_cancel.textContent = "Cancel"
            btn_cancel.onclick = create_proxy(lambda _evt=None: self.cancel_attack_plan())

            btn_confirm = js.document.createElement("button")
            btn_confirm.className = "hexengine-attack-controls__confirm"
            btn_confirm.textContent = "Confirm attack"
            btn_confirm.disabled = True
            btn_confirm.onclick = create_proxy(lambda _evt=None: self.confirm_attack_plan())

            row.appendChild(btn_cancel)
            row.appendChild(btn_confirm)
            root.appendChild(row)

            primary_actions_host.appendChild(root)
            self._attack_controls_root = root
            self._attack_controls_status = status
            self._attack_controls_confirm = btn_confirm
            self._attack_controls_cancel = btn_cancel
        except Exception:
            self.logger.debug("attack controls init failed", exc_info=True)

    def _ensure_attack_target_overlay(self):
        layer = self.canvas.ensure_overlay_layer()
        if layer is None:
            return None
        if self._attack_plan_target_overlay is None:
            div = js.document.createElement("div")
            div.className = "hexengine-map-overlay hexengine-map-overlay--glyph"
            div.style.pointerEvents = "none"
            div.style.position = "absolute"
            div.style.transform = "translate(-50%, -50%)"
            div.style.zIndex = "450"
            div.textContent = "⊕"
            layer.appendChild(div)
            self._attack_plan_target_overlay = div
        return self._attack_plan_target_overlay

    def _ensure_attack_los_svg_group(self):
        """
        Ensure an SVG group exists for attack-plan LOS lines.

        Lines live on the **unit** SVG (same map-space size as hex highlights) so they
        paint above counters. The group is re-appended to the end of that SVG whenever
        lines sync so it stays on top after ``DisplayManager`` reorders unit nodes.
        """
        try:
            svg = self.canvas.unit_layer._svg
        except Exception:
            return None
        if svg is None:
            return None
        g = self._attack_plan_los_svg_group
        if g is not None:
            try:
                if getattr(g, "parentNode", None) is not svg:
                    try:
                        g.remove()
                    except Exception:
                        pass
                    self._attack_plan_los_svg_group = None
            except Exception:
                self._attack_plan_los_svg_group = None
        if self._attack_plan_los_svg_group is None:
            g = js.document.createElementNS("http://www.w3.org/2000/svg", "g")
            g.classList.add("hexengine-attack-los-layer")
            g.style.pointerEvents = "none"
            svg.appendChild(g)
            self._attack_plan_los_svg_group = g
        return self._attack_plan_los_svg_group

    def _clear_attack_los_lines(self) -> None:
        for _uid, node in list(self._attack_plan_los_lines.items()):
            try:
                node.remove()
            except Exception:
                pass
        self._attack_plan_los_lines.clear()

    def _segment_intersection_with_polygon(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        poly: list[tuple[float, float]],
    ) -> tuple[float, float] | None:
        """
        Return nearest intersection point between segment (x1,y1)-(x2,y2) and polygon edges.

        Polygon is provided as a list of vertices in order (closed implicitly).
        """

        def cross(ax: float, ay: float, bx: float, by: float) -> float:
            return ax * by - ay * bx

        rx, ry = (x2 - x1), (y2 - y1)
        best_t: float | None = None
        best_pt: tuple[float, float] | None = None
        n = len(poly)
        if n < 3:
            return None
        for i in range(n):
            (px, py) = poly[i]
            (qx, qy) = poly[(i + 1) % n]
            sx, sy = (qx - px), (qy - py)
            denom = cross(rx, ry, sx, sy)
            if abs(denom) < 1e-9:
                continue  # Parallel or collinear; ignore.
            qpx, qpy = (px - x1), (py - y1)
            t = cross(qpx, qpy, sx, sy) / denom
            u = cross(qpx, qpy, rx, ry) / denom
            if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
                if best_t is None or t < best_t:
                    best_t = t
                    best_pt = (x1 + rx * t, y1 + ry * t)
        return best_pt

    def _sync_attack_plan_los_lines(self, st: GameState | None) -> None:
        """Render LOS lines for ranged attackers toward the current target hex."""
        if st is None or self.attack_plan_target_hex is None:
            self._clear_attack_los_lines()
            return
        tgt = self.attack_plan_target_hex
        g = self._ensure_attack_los_svg_group()
        if g is None:
            return

        tx, ty = self.canvas.hex_layout.hex_to_pixel(tgt)

        from ..hexes.los import first_blocking_hex

        def blocks(h):
            loc = st.board.effective_location(h)
            if loc is None:
                return False
            return bool(getattr(loc, "block_los", False))

        keep: set[str] = set()
        for uid in sorted(self.attack_plan_attacker_ids):
            u = st.board.units.get(uid)
            if u is None or not u.active:
                continue
            ut = str(getattr(u, "unit_type", "")).lower()
            if ut not in ("artillery", "art"):
                continue
            try:
                atk_range = int(u.attributes.get("range", 0))
            except Exception:
                atk_range = 0
            if atk_range <= 1:
                continue

            ax, ay = self.canvas.hex_layout.hex_to_pixel(u.position)
            endx, endy = (tx, ty)
            blocked_hex = first_blocking_hex(u.position, tgt, blocks=blocks)
            is_blocked = blocked_hex is not None
            if blocked_hex is not None:
                try:
                    corners = self.canvas.hex_layout.hex_corners(blocked_hex)
                    hit = self._segment_intersection_with_polygon(
                        ax, ay, tx, ty, [(float(x), float(y)) for x, y in corners]
                    )
                    if hit is not None:
                        endx, endy = hit
                except Exception:
                    pass

            line = self._attack_plan_los_lines.get(uid)
            if line is None:
                line = js.document.createElementNS("http://www.w3.org/2000/svg", "line")
                line.classList.add("hexengine-attack-los-line")
                line.setAttribute("data-unit", str(uid))
                g.appendChild(line)
                self._attack_plan_los_lines[uid] = line
            line.setAttribute("x1", str(float(ax)))
            line.setAttribute("y1", str(float(ay)))
            line.setAttribute("x2", str(float(endx)))
            line.setAttribute("y2", str(float(endy)))
            if is_blocked:
                line.classList.add("hexengine-attack-los-line--blocked")
            else:
                line.classList.remove("hexengine-attack-los-line--blocked")
            keep.add(uid)

        # Remove stale lines.
        for uid in list(self._attack_plan_los_lines.keys()):
            if uid not in keep:
                try:
                    self._attack_plan_los_lines[uid].remove()
                except Exception:
                    pass
                self._attack_plan_los_lines.pop(uid, None)

        # Keep the LOS layer after all unit `<g>` nodes so strokes paint on top.
        try:
            self.canvas.unit_layer._svg.appendChild(g)
        except Exception:
            pass

    def _sync_attack_plan_ui(self) -> None:
        st = self._interactive_game_state()
        ok_phase = _phase_allows_attack_planning(
            str(getattr(getattr(st, "turn", None), "current_phase", "")) if st else ""
        )

        tgt = self.attack_plan_target_hex
        n_att = len(self.attack_plan_attacker_ids)

        # Secondary selection visuals: selected attackers + all units on the target hex.
        attacker_ids = set(self.attack_plan_attacker_ids)
        target_unit_ids: set[str] = set()
        if st is not None and tgt is not None:
            try:
                for u in st.board.active_units_at_hex(tgt):
                    target_unit_ids.add(str(u.unit_id))
            except Exception:
                target_unit_ids = set()
        self.ui_state.set_secondary_selected_units(attacker_ids)
        self.ui_state.set_secondary_target_units(target_unit_ids)
        self.display_mgr.sync_secondary_selection(
            attacker_ids,
            target_unit_ids=target_unit_ids,
        )
        self._sync_attack_plan_los_lines(st)

        if self._attack_controls_status is not None:
            if not ok_phase:
                self._attack_controls_status.textContent = "Not in Combat phase."
            elif tgt is None:
                self._attack_controls_status.textContent = "Combat: pick a target hex."
            else:
                self._attack_controls_status.textContent = (
                    f"Target set. Selected attackers: {n_att}. Click units to add/remove."
                )

        if self._attack_controls_confirm is not None:
            self._attack_controls_confirm.disabled = not (ok_phase and tgt is not None and n_att > 0)

    def _attack_target_hex_has_enemy(self, st: GameState, h: "Hex") -> bool:
        """True if the hex has at least one active non-current-faction unit (valid attack target)."""
        cur = st.turn.current_faction
        return any(u.faction != cur for u in st.board.active_units_at_hex(h))

    def set_attack_plan_target_hex(self, h: "Hex | None") -> None:
        if h is not None:
            st = self._interactive_game_state()
            if st is not None and not self._attack_target_hex_has_enemy(st, h):
                try:
                    mx, my = self.canvas.hex_layout.hex_to_pixel(h)
                    cx, cy = self.canvas.map_space_to_container_pixel(mx, my)
                    self.popup_manager.create_popup("No enemy unit on that hex", (cx, cy))
                except Exception:
                    self.popup_manager.create_popup("No enemy unit on that hex", (32, 32))
                return
        self.attack_plan_target_hex = h
        self.attack_plan_attacker_ids.clear()

        ov = self._ensure_attack_target_overlay()
        if ov is not None and h is not None:
            mx, my = self.canvas.hex_layout.hex_to_pixel(h)
            ov.style.left = f"{mx}px"
            ov.style.top = f"{my}px"
            ov.style.display = "block"
        elif ov is not None:
            ov.style.display = "none"

        self._sync_attack_plan_ui()

    def cancel_attack_plan(self) -> None:
        self.set_attack_plan_target_hex(None)
        self.ui_state.clear_secondary_selection()
        self.display_mgr.clear_secondary_selection()
        self._clear_attack_los_lines()

    def _attack_unit_is_eligible(self, st, unit_id: str) -> bool:
        if st is None or self.attack_plan_target_hex is None:
            return False
        if not self._attack_target_hex_has_enemy(st, self.attack_plan_target_hex):
            return False
        u = st.board.units.get(unit_id)
        if u is None or not u.active:
            return False
        if u.faction != st.turn.current_faction:
            return False
        from ..hexes.math import distance
        from ..hexes.los import has_line_of_sight

        target_hex = self.attack_plan_target_hex
        ut = str(u.unit_type).lower()
        d = distance(u.position, target_hex)
        if ut in ("infantry", "inf"):
            return d == 1
        if ut in ("artillery", "art"):
            try:
                atk_range = int(u.attributes.get("range", 0))
            except Exception:
                atk_range = 0
            if not (atk_range > 1 and d > 1 and d <= atk_range):
                return False

            def blocks(h):
                loc = st.board.effective_location(h)
                if loc is None:
                    return False
                return bool(getattr(loc, "block_los", False))

            return has_line_of_sight(u.position, target_hex, blocks=blocks)
        return False

    def toggle_attack_plan_attacker(self, unit_id: str) -> None:
        st = self._interactive_game_state()
        if self.attack_plan_target_hex is None or st is None:
            return
        if unit_id in self.attack_plan_attacker_ids:
            self.attack_plan_attacker_ids.remove(unit_id)
            self._sync_attack_plan_ui()
            return
        if self._attack_unit_is_eligible(st, unit_id):
            self.attack_plan_attacker_ids.add(unit_id)
        else:
            msg = "Cannot attack target"
            try:
                u = st.board.units.get(unit_id)
                tgt = self.attack_plan_target_hex
                if u is not None and tgt is not None:
                    ut = str(getattr(u, "unit_type", "")).lower()
                    if ut in ("artillery", "art"):
                        from ..hexes.math import distance
                        from ..hexes.los import has_line_of_sight

                        d = distance(u.position, tgt)
                        try:
                            atk_range = int(u.attributes.get("range", 0))
                        except Exception:
                            atk_range = 0
                        if atk_range <= 1:
                            msg = "No ranged capability"
                        elif d <= 1:
                            msg = "Target too close for ranged fire"
                        elif d > atk_range:
                            msg = "Target out of range"
                        else:
                            # In distance band (not adjacent, within max range); check LOS.
                            def blocks(h):
                                loc = st.board.effective_location(h)
                                if loc is None:
                                    return False
                                return bool(getattr(loc, "block_los", False))

                            if not has_line_of_sight(u.position, tgt, blocks=blocks):
                                msg = "No line of sight"
            except Exception:
                pass
            # Show a short callout near the unit (fall back to generic if missing display).
            try:
                disp = self.display_mgr.get_display(unit_id)
                if disp is not None:
                    mx, my = self.canvas.hex_layout.hex_to_pixel(disp.position)
                    cx, cy = self.canvas.map_space_to_container_pixel(mx, my)
                    self.popup_manager.create_popup(msg, (cx, cy))
                else:
                    self.popup_manager.create_popup(msg, (32, 32))
            except Exception:
                self.popup_manager.create_popup(msg, (32, 32))
        self._sync_attack_plan_ui()

    def confirm_attack_plan(self) -> None:
        st = self._interactive_game_state()
        if st is None or self.attack_plan_target_hex is None:
            return
        if not self.attack_plan_attacker_ids:
            return

        defenders = [
            u
            for u in st.board.active_units_at_hex(self.attack_plan_target_hex)
            if u.faction != st.turn.current_faction
        ]
        if not defenders:
            try:
                mx, my = self.canvas.hex_layout.hex_to_pixel(self.attack_plan_target_hex)
                cx, cy = self.canvas.map_space_to_container_pixel(mx, my)
                self.popup_manager.create_popup("No enemy unit on target", (cx, cy))
            except Exception:
                self.popup_manager.create_popup("No enemy unit on target", (32, 32))
            return
        defender_id = defenders[-1].unit_id
        defender_ids = sorted(str(u.unit_id) for u in defenders)

        attacker_ids = sorted(self.attack_plan_attacker_ids)
        primary_attacker_id = attacker_ids[0]

        tgt = self.attack_plan_target_hex
        seen_att: set[tuple[int, int, int]] = set()
        attacker_hexes_wire: list[dict[str, int]] = []
        for uid in attacker_ids:
            u = st.board.units.get(uid)
            if u is None or not u.active:
                continue
            t = (int(u.position.i), int(u.position.j), int(u.position.k))
            if t in seen_att:
                continue
            seen_att.add(t)
            attacker_hexes_wire.append({"i": t[0], "j": t[1], "k": t[2]})
        attacker_hexes_wire.sort(key=lambda d: (d["i"], d["j"], d["k"]))
        defender_hexes_wire = [
            {"i": int(tgt.i), "j": int(tgt.j), "k": int(tgt.k)},
        ]

        self.execute_action_request(
            "Attack",
            {
                "attack_kind": "combined",
                "attacker_id": primary_attacker_id,
                "attacker_ids": attacker_ids,
                "defender_id": defender_id,
                "defender_ids": defender_ids,
                "attacker_hexes": attacker_hexes_wire,
                "defender_hexes": defender_hexes_wire,
            },
        )
        self.cancel_attack_plan()

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
                game_def = load_game_definition_for_scenario(scenario_path)
                self._local_game_definition = game_def
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
            self.client.on_ui_popup = self._handle_ui_popup
            self.client.on_marker_preview = self._handle_marker_preview
            self.client.on_unit_preview = self._handle_unit_preview

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
        self._local_game_definition = None
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
        self.execute_action_request(action_type, params)

    def execute_action_request(self, action_type: str, params: dict[str, Any]) -> None:
        """Send an already-serialized action request to the server."""
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
        client = getattr(self, "client", None)
        if client is not None:
            tr = getattr(client, "turn_rules", None)
            if isinstance(tr, dict):
                raw = tr.get("title_state_extension_key")
                if isinstance(raw, str) and raw.strip():
                    return raw.strip()
        gd = getattr(self, "_title_game_definition", None)
        if gd is not None:
            k = getattr(gd, "title_state_extension_key", None)
            if isinstance(k, str) and k.strip():
                return k.strip()
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
        self._sync_interaction_messages()
        self._apply_title_faction_css()
        self._apply_focus_unit_after_state_sync(new_state)
        self._sync_attack_plan_after_state_update()

    def _sync_interaction_messages(self) -> None:
        """Render per-recipient `StateUpdate.interaction_messages` as a small banner."""
        from ..document import element, js, jsnull

        client = self.client
        msgs = client.interaction_messages if client is not None else None
        rows = [m for m in msgs if isinstance(m, dict)] if isinstance(msgs, list) else []
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
        if not rows:
            # Clear if present.
            el = js.document.getElementById("interaction-banner")
            if el is not None and el is not jsnull:
                el.innerText = ""
                el.className = ""
            return

        def _prio(kind: str) -> int:
            return {"retreat": 30, "wait": 20, "phase": 10, "info": 5, "error": 40}.get(kind, 0)

        best: dict[str, Any] | None = None
        best_p = -1
        for r in rows:
            t = r.get("text")
            if not isinstance(t, str) or not t.strip():
                continue
            kraw = r.get("kind")
            k = str(kraw).strip() if kraw is not None else ""
            p = _prio(k)
            if p >= best_p:
                best_p = p
                best = r
        if best is None:
            return
        text = str(best.get("text", "")).strip()
        kind = str(best.get("kind", "")).strip()
        extra_cls = best.get("css_class")
        extra_cls = str(extra_cls).strip() if isinstance(extra_cls, str) and extra_cls.strip() else ""

        banner = js.document.getElementById("interaction-banner")
        if banner is None or banner is jsnull:
            ui = element("ui-panel")
            if ui is None:
                return
            banner = js.document.createElement("div")
            banner.id = "interaction-banner"
            ui.appendChild(banner)

        banner.innerText = text
        base = (
            "interaction-msg--retreat"
            if kind == "retreat"
            else "interaction-msg--wait"
            if kind == "wait"
            else "interaction-msg--phase"
            if kind == "phase"
            else ""
        )
        # Also apply the title's faction css class so titles can style phase banners.
        fac = ""
        st = self.action_mgr.current_state
        if st is not None:
            fac = str(st.turn.current_faction)
        _, faction_cls = self._faction_ui_for(fac)
        banner.className = " ".join(
            c for c in (base, extra_cls, faction_cls or "") if c
        ).strip()

    def _set_engine_banner_message(
        self,
        *,
        kind: str,
        text: str,
        ttl_ms: int | None,
        css_class: str | None = None,
    ) -> None:
        """Local-only banner message for engine/runtime failures (not title-controlled)."""
        from ..document import create_proxy, js

        now_ms = int(js.Date.now())
        self._engine_banner_message = {
            "schema": 1,
            "kind": str(kind),
            "text": str(text),
            "dedupe_key": "engine",
            "ttl_ms": ttl_ms,
            "css_class": str(css_class).strip()
            if isinstance(css_class, str) and css_class.strip()
            else None,
            "_received_at_ms": now_ms,
        }
        # If this message has a TTL, schedule a re-sync so it can disappear without
        # waiting for the next server StateUpdate.
        if isinstance(ttl_ms, int) and ttl_ms >= 0:
            js.setTimeout(create_proxy(lambda: self._sync_interaction_messages()), ttl_ms + 50)

    def _faction_ui_for(self, faction_id: str) -> tuple[str, str | None]:
        """
        Resolve (label, css_class) for faction_id from server turn_rules.

        Falls back to display_faction_name and no explicit css class.
        """
        tr = self.client.turn_rules if self.client is not None else None
        if isinstance(tr, dict):
            ui = tr.get("faction_ui")
            if isinstance(ui, dict):
                facs = ui.get("factions")
                if isinstance(facs, list):
                    for row in facs:
                        if not isinstance(row, dict):
                            continue
                        if str(row.get("id", "")) != str(faction_id):
                            continue
                        label = row.get("label")
                        cssc = row.get("css_class")
                        out_label = (
                            str(label).strip()
                            if isinstance(label, str) and label.strip()
                            else display_faction_name(faction_id)
                        )
                        out_css = (
                            str(cssc).strip()
                            if isinstance(cssc, str) and cssc.strip()
                            else None
                        )
                        return out_label, out_css
        return display_faction_name(faction_id), None

    def _apply_title_faction_css(self) -> None:
        """Inject optional title CSS from turn_rules.faction_ui (inline + href)."""
        from ..document import js, jsnull

        client = self.client
        tr = client.turn_rules if client is not None else None
        css: str | None = None
        css_href: str | None = None
        if isinstance(tr, dict):
            ui = tr.get("faction_ui")
            if isinstance(ui, dict):
                raw = ui.get("css")
                if isinstance(raw, str) and raw.strip():
                    css = raw
                rh = ui.get("css_href")
                if isinstance(rh, str) and rh.strip():
                    css_href = rh.strip()
        css_norm = css.strip() if isinstance(css, str) else ""
        if (
            getattr(self, "_applied_title_css", None) == css_norm
            and getattr(self, "_applied_title_css_href", None) == (css_href or "")
        ):
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
        """Apply per-viewer StateUpdate.suggested_focus_unit_id when valid."""
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

    def _handle_ui_popup(self, payload: dict[str, Any]) -> None:
        """
        Title-formatted informational popup.

        This is separate from the interaction banner. It is meant for lightweight
        inspection UX (unit/marker), and can be overridden by title hooks.
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
        if html:
            self.popup_manager.create_popup_html(html, pos)
        else:
            self.popup_manager.create_popup(text, pos)

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
        c = self.client
        tr = c.turn_rules if c is not None else None
        if not isinstance(tr, dict):
            return None
        raw = tr.get("max_active_units_per_hex")
        try:
            n = int(raw)
        except (TypeError, ValueError):
            return None
        return n if n > 0 else None

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
        # Ask authoritative server for destination preview hexes so thin clients match.
        if self.client is not None:
            self.client.send_unit_preview_request(unit_id)
            # The websocket client increments its own counter; capture the latest id.
            self._unit_preview_request_id = str(getattr(self.client, "_preview_req_counter", ""))
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
        if isinstance(rid, str) and self._unit_preview_request_id and rid != self._unit_preview_request_id:
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
            c = self.client
            if c is not None and isinstance(c.turn_rules, dict):
                ui = c.turn_rules.get("ui")
                if isinstance(ui, dict):
                    kind = str(payload.get("kind", "")).strip()
                    key = "retreat_hex_class" if kind == "retreat" else "move_hex_class"
                    raw = ui.get(key)
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
            self._marker_preview_request_id = str(getattr(self.client, "_preview_req_counter", ""))
        valid: set[Any] = set()
        self.ui_state.set_constraints(valid)
        cls = "highlight"
        c = self.client
        if c is not None and isinstance(c.turn_rules, dict):
            ui = c.turn_rules.get("ui")
            if isinstance(ui, dict):
                raw = ui.get("marker_hex_class")
                if isinstance(raw, str) and raw.strip():
                    cls = raw.strip()
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
        if isinstance(rid, str) and self._marker_preview_request_id and rid != self._marker_preview_request_id:
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
            c = self.client
            if c is not None and isinstance(c.turn_rules, dict):
                ui = c.turn_rules.get("ui")
                if isinstance(ui, dict):
                    raw = ui.get("marker_hex_class")
                    if isinstance(raw, str) and raw.strip():
                        cls = raw.strip()
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
