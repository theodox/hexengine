"""
Optional client combat UX (attack planning) gated by `turn_rules.client_contract`.

Attack-plan draft input is client-local until commit. The client sends snapshots
via ``map_selection_preview`` when ``map_selection_previews`` is advertised;
confirm/cancel merge into the turn action dock via ``panel_actions``. Gate
buttons derive from ``current_segment`` on the server dock wire.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...document import js
from ...hexes.types import Hex
from ...state import GameState
from .client_map_selection import ClientMapSelectionMixin

if TYPE_CHECKING:
    pass


class ClientCombatMixin(ClientMapSelectionMixin):
    """Attack-planning UI mixed into `Game` when the title enables combat on the wire."""

    attack_plan_target_hex: Hex | None
    attack_plan_attacker_ids: set[str]
    _attack_plan_suppress_bg_mouseup_retarget: bool
    _attack_plan_target_overlay: Any
    _attack_plan_los_svg_group: Any
    _attack_plan_los_lines: dict[str, Any]

    def _client_has_attack_planning_ui(self) -> bool:
        return (
            "attack_planning_ui" in self._client_title_data().client_contract_features
        )

    def _attack_planning_allowed(self) -> bool:
        """True when server ``current_segment`` allows ``Attack``."""

        allowed = self._segment_allows_action("Attack")
        return allowed is True

    def _shell_attack_copy(self, key: str, default: str) -> str:
        su = self._client_title_data().shell_ui
        raw = getattr(su, key, None)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        return default

    def _current_segment_wire(self) -> dict[str, Any] | None:
        client = getattr(self, "client", None)
        if client is None:
            return None
        seg = getattr(client, "current_segment", None)
        return dict(seg) if isinstance(seg, dict) else None

    def _segment_allows_action(self, action_type: str) -> bool | None:
        """True/False from server ``current_segment``; None when descriptor absent."""

        from ...arcs.segment_wire import segment_allows_action

        seg = self._current_segment_wire()
        if seg is None:
            return None
        return segment_allows_action(seg, action_type)

    def _segment_blocks_attack_planning_ui(self) -> bool:
        return not self._attack_planning_allowed()

    def _sync_attack_plan_after_state_update(self) -> None:
        if not self._client_has_attack_planning_ui():
            if self.attack_plan_target_hex is not None or self.attack_plan_attacker_ids:
                self.cancel_attack_plan()
            return
        if self._segment_blocks_attack_planning_ui():
            if self.attack_plan_target_hex is not None or self.attack_plan_attacker_ids:
                self.cancel_attack_plan()
            return
        if self.attack_plan_target_hex is None and not self.attack_plan_attacker_ids:
            self._request_attack_plan_preview()
            self._sync_attack_plan_ui()
            return
        st = self._interactive_game_state()
        if st is None:
            self.cancel_attack_plan()
            return
        planning_ok = self._attack_planning_allowed()
        my_turn = True
        client = getattr(self, "client", None)
        if client is not None and client.is_connected() and client.faction:
            my_turn = self.is_my_turn()
        if not planning_ok or not my_turn:
            self.cancel_attack_plan()
            return
        tgt = self.attack_plan_target_hex
        if tgt is not None and not self._attack_target_hex_has_enemy(st, tgt):
            self.cancel_attack_plan()
            return
        self._sync_attack_plan_ui()

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
                continue
            qpx, qpy = (px - x1), (py - y1)
            t = cross(qpx, qpy, sx, sy) / denom
            u = cross(qpx, qpy, rx, ry) / denom
            if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
                if best_t is None or t < best_t:
                    best_t = t
                    best_pt = (x1 + rx * t, y1 + ry * t)
        return best_pt

    def _sync_attack_plan_los_lines(self, st: GameState | None) -> None:
        if st is None or self.attack_plan_target_hex is None:
            self._clear_attack_los_lines()
            return
        tgt = self.attack_plan_target_hex
        g = self._ensure_attack_los_svg_group()
        if g is None:
            return

        tx, ty = self.canvas.hex_layout.hex_to_pixel(tgt)

        from ...hexes.los import first_blocking_hex
        from ...state.map_feature_queries import edges_block_los_predicate

        def blocks(h):
            loc = st.board.effective_location(h)
            if loc is None:
                return False
            return bool(getattr(loc, "block_los", False))

        edges_block = edges_block_los_predicate(st.board)

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
            blocked_hex = first_blocking_hex(
                u.position, tgt, blocks=blocks, edges_block=edges_block
            )
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

        for uid in list(self._attack_plan_los_lines.keys()):
            if uid not in keep:
                try:
                    self._attack_plan_los_lines[uid].remove()
                except Exception:
                    pass
                self._attack_plan_los_lines.pop(uid, None)

        try:
            self.canvas.unit_layer._svg.appendChild(g)
        except Exception:
            pass

    def _sync_attack_plan_ui(self) -> None:
        st = self._interactive_game_state()
        tgt = self.attack_plan_target_hex

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

        self._refresh_turn_action_dock_actions()

    def _attack_target_hex_has_enemy(self, st: GameState, h: Hex) -> bool:
        cur = st.turn.current_faction
        return any(u.faction != cur for u in st.board.active_units_at_hex(h))

    def set_attack_plan_target_hex(self, h: Hex | None) -> None:
        if not self._client_has_attack_planning_ui():
            return
        if h is not None and self._client_has_map_selection_previews():
            valid = self._attack_plan_valid_target_hexes()
            if valid:
                t = (int(h.i), int(h.j), int(h.k))
                if t not in valid:
                    self.show_inform_popup("", "no_attackable_enemy", hex=h)
                    return
        elif h is not None:
            st = self._interactive_game_state()
            if st is not None and not self._attack_target_hex_has_enemy(st, h):
                self.show_inform_popup("", "no_enemy_on_hex", hex=h)
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

        self._request_attack_plan_preview()
        self._sync_attack_plan_ui()

    def cancel_attack_plan(self) -> None:
        self._map_selection_preview = None
        self.set_attack_plan_target_hex(None)
        self._refresh_turn_action_dock_actions()
        self.ui_state.clear_secondary_selection()
        self.display_mgr.clear_secondary_selection()
        self._clear_attack_los_lines()

    def toggle_attack_plan_attacker(self, unit_id: str) -> None:
        if not self._client_has_attack_planning_ui():
            return
        st = self._interactive_game_state()
        if self.attack_plan_target_hex is None or st is None:
            return
        if unit_id in self.attack_plan_attacker_ids:
            self.attack_plan_attacker_ids.remove(unit_id)
        elif unit_id in self._attack_plan_eligible_attacker_ids():
            self.attack_plan_attacker_ids.add(unit_id)
        else:
            self.show_inform_popup(
                "",
                "cannot_attack_target",
                unit_id=str(unit_id),
            )
        self._request_attack_plan_preview()
        self._sync_attack_plan_ui()

    def confirm_attack_plan(self) -> None:
        if not self._client_has_attack_planning_ui():
            return
        prev = getattr(self, "_map_selection_preview", None)
        if isinstance(prev, dict):
            payload = prev.get("commit_payload")
            if isinstance(payload, dict) and prev.get("confirm_enabled"):
                self._commit_attack_plan(payload)
                return
        if not self._attack_plan_confirm_enabled():
            return


__all__ = ["ClientCombatMixin"]
