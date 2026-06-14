"""
Retreat path map-selection (click-to-extend) mixed into ``Game``.

Used when the title binds ``MovementHook.RETREAT_PATH_PREVIEW`` and the viewer has a
retreat obligation on the selected unit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...document import js
from ...gamedef.interactions import InteractionKind
from ...hexes.types import Hex
from ...state import GameState

if TYPE_CHECKING:
    pass


class ClientRetreatPathMixin:
    """Path draft state, preview highlights, and stepwise continuation after confirm."""

    retreat_path_unit_id: str | None
    retreat_path_hexes: list[Any]
    retreat_path_committed: tuple[Hex, ...] | None
    retreat_path_continue_index: int
    _retreat_path_svg_group: Any
    _retreat_path_polyline_el: Any

    def _ensure_retreat_path_svg_group(self):
        try:
            svg = self.canvas.svg_layer._svg
        except Exception:
            return None
        if svg is None:
            return None
        g = getattr(self, "_retreat_path_svg_group", None)
        if g is not None:
            try:
                if getattr(g, "parentNode", None) is not svg:
                    try:
                        g.remove()
                    except Exception:
                        pass
                    self._retreat_path_svg_group = None
                    self._retreat_path_polyline_el = None
            except Exception:
                self._retreat_path_svg_group = None
                self._retreat_path_polyline_el = None
        if self._retreat_path_svg_group is None:
            g = js.document.createElementNS("http://www.w3.org/2000/svg", "g")
            g.classList.add("hexengine-retreat-path-layer")
            g.style.pointerEvents = "none"
            svg.appendChild(g)
            self._retreat_path_svg_group = g
        else:
            try:
                svg.appendChild(self._retreat_path_svg_group)
            except Exception:
                pass
        return self._retreat_path_svg_group

    def _retreat_path_polyline_hexes(
        self, payload: dict[str, Any] | None = None
    ) -> list[Hex]:
        """Prefer the local draft; fall back to server ``preview_path_hexes``."""
        local = [
            h
            for h in (getattr(self, "retreat_path_hexes", None) or [])
            if isinstance(h, Hex)
        ]
        wire: list[Hex] = []
        if isinstance(payload, dict):
            wire = self._hexes_from_wire_rows(payload.get("preview_path_hexes"))
        if len(local) >= len(wire):
            return local
        return wire

    def _sync_retreat_path_polyline(self, path: list[Hex] | None = None) -> None:
        if path is None:
            path = [
                h
                for h in (getattr(self, "retreat_path_hexes", None) or [])
                if isinstance(h, Hex)
            ]
        if len(path) < 2:
            self._clear_retreat_path_polyline()
            return
        g = self._ensure_retreat_path_svg_group()
        if g is None:
            return
        layout = self.canvas.hex_layout
        pts: list[str] = []
        for h in path:
            x, y = layout.hex_to_pixel(h)
            pts.append(f"{float(x)},{float(y)}")
        poly = getattr(self, "_retreat_path_polyline_el", None)
        if poly is not None:
            try:
                if getattr(poly, "parentNode", None) is None:
                    poly = None
                    self._retreat_path_polyline_el = None
            except Exception:
                poly = None
                self._retreat_path_polyline_el = None
        if poly is None:
            poly = js.document.createElementNS("http://www.w3.org/2000/svg", "polyline")
            poly.classList.add("hexengine-retreat-path-line")
            poly.setAttribute("fill", "none")
            g.appendChild(poly)
            self._retreat_path_polyline_el = poly
        poly.setAttribute("points", " ".join(pts))

    def _clear_retreat_path_polyline(self) -> None:
        el = getattr(self, "_retreat_path_polyline_el", None)
        if el is not None:
            try:
                el.remove()
            except Exception:
                pass
            self._retreat_path_polyline_el = None

    @staticmethod
    def _hexes_from_wire_rows(raw: Any) -> list[Hex]:
        if not isinstance(raw, list):
            return []
        out: list[Hex] = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            try:
                out.append(Hex(int(row["i"]), int(row["j"]), int(row["k"])))
            except (KeyError, TypeError, ValueError):
                continue
        return out

    def _client_has_retreat_path_selection(self) -> bool:
        return InteractionKind.RETREAT_PATH in (
            self._map_selection_preview_handlers().keys()
        )

    def _retreat_path_active(self) -> bool:
        if not self._client_has_retreat_path_selection():
            return False
        uid = getattr(self, "retreat_path_unit_id", None)
        if not isinstance(uid, str) or not uid.strip():
            return False
        st = self._interactive_game_state()
        if st is None:
            return False
        return self.retreat_obligation_hexes_remaining(st, uid) is not None

    def _retreat_path_draft_wire(self) -> dict[str, Any]:
        uid = str(getattr(self, "retreat_path_unit_id", "") or "").strip()
        raw_path = getattr(self, "retreat_path_hexes", None) or []
        path_wire: list[dict[str, int]] = []
        for h in raw_path:
            if isinstance(h, Hex):
                path_wire.append({"i": int(h.i), "j": int(h.j), "k": int(h.k)})
        return {"unit_id": uid, "path": path_wire}

    def cancel_retreat_path(self) -> None:
        self.retreat_path_unit_id = None
        self.retreat_path_hexes = []
        self.retreat_path_committed = None
        self.retreat_path_continue_index = 0
        self._map_selection_preview = None
        self._clear_retreat_path_polyline()
        self.display_mgr.clear_highlights()
        self._refresh_turn_action_dock_actions()

    def begin_retreat_path_for_unit(self, unit_id: str) -> None:
        st = self._interactive_game_state()
        if st is None:
            return
        uid = str(unit_id).strip()
        if self.retreat_obligation_hexes_remaining(st, uid) is None:
            return
        u = st.board.units.get(uid)
        if u is None:
            return
        self.retreat_path_unit_id = uid
        self.retreat_path_hexes = [u.position]
        self.retreat_path_committed = None
        self.retreat_path_continue_index = 0
        self._clear_drag_and_highlights()
        self.ui_state.select_unit(uid)
        gu = self.board.get_unit(uid)
        if gu is not None:
            self.selection = gu
        self._refresh_retreat_path_preview()

    def _refresh_retreat_path_preview(self) -> None:
        """Re-request server preview (hex highlights) for the active retreat-path draft."""
        if not self._retreat_path_active():
            return
        self._request_map_selection_preview(
            InteractionKind.RETREAT_PATH, self._retreat_path_draft_wire()
        )

    def _sync_retreat_obligation_unit_highlights(self, state: GameState) -> None:
        """Secondary-select every unit on this viewer's faction that owes a retreat."""
        client = getattr(self, "client", None)
        ro = (
            getattr(client, "retreat_obligations", None) if client is not None else None
        )
        if not isinstance(ro, dict) or not ro:
            return
        fac = str(getattr(client, "faction", "") or "").strip()
        ids: set[str] = set()
        for uid, raw in ro.items():
            uid_s = str(uid).strip()
            if not uid_s:
                continue
            try:
                if int(raw) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            u = state.board.units.get(uid_s)
            if u is None or not u.active:
                continue
            if fac and str(u.faction).strip() != fac:
                continue
            ids.add(uid_s)
        if not ids:
            return
        self.ui_state.set_secondary_selected_units(ids)
        self.display_mgr.sync_secondary_selection(ids)

    def append_retreat_path_hex(self, h: Hex) -> None:
        if not self._retreat_path_active():
            return
        legal = self._retreat_path_legal_next_hexes()
        if h not in legal:
            return
        path = list(getattr(self, "retreat_path_hexes", None) or [])
        if path and path[-1] == h:
            return
        path.append(h)
        self.retreat_path_hexes = path
        self._sync_retreat_path_polyline(path)
        self._request_map_selection_preview(
            InteractionKind.RETREAT_PATH, self._retreat_path_draft_wire()
        )

    def undo_retreat_path_hex(self) -> None:
        if not self._retreat_path_active():
            return
        path = list(getattr(self, "retreat_path_hexes", None) or [])
        if len(path) <= 1:
            return
        path.pop()
        self.retreat_path_hexes = path
        self._sync_retreat_path_polyline(path)
        self._request_map_selection_preview(
            InteractionKind.RETREAT_PATH, self._retreat_path_draft_wire()
        )

    def _retreat_path_legal_next_hexes(self) -> set[Hex]:
        prev = getattr(self, "_map_selection_preview", None)
        if not isinstance(prev, dict):
            return set()
        raw = prev.get("legal_next_hexes")
        if not isinstance(raw, list):
            return set()
        out: set[Hex] = set()
        for row in raw:
            if not isinstance(row, dict):
                continue
            try:
                out.add(Hex(int(row["i"]), int(row["j"]), int(row["k"])))
            except (KeyError, TypeError, ValueError):
                continue
        return out

    def _apply_retreat_path_preview(self, payload: dict[str, Any]) -> None:
        self.display_mgr.clear_highlights()
        hi = self._client_title_data().hex_highlights
        path_cls = (
            hi.retreat_through_hex_class
            if isinstance(hi.retreat_through_hex_class, str)
            and hi.retreat_through_hex_class.strip()
            else hi.retreat_hex_class or "highlight"
        )
        tip_cls = (
            hi.retreat_hex_class
            if isinstance(hi.retreat_hex_class, str) and hi.retreat_hex_class.strip()
            else "highlight"
        )

        through: set[Hex] = set()
        raw_through = payload.get("through_hexes")
        if isinstance(raw_through, list):
            for row in raw_through:
                if isinstance(row, dict):
                    try:
                        through.add(Hex(int(row["i"]), int(row["j"]), int(row["k"])))
                    except (KeyError, TypeError, ValueError):
                        pass
        path_hexes = self._retreat_path_polyline_hexes(payload)
        if len(path_hexes) >= 2:
            for h in path_hexes[:-1]:
                through.add(h)
        if through:
            self.display_mgr.highlight_hexes(through, cls=path_cls)

        legal: set[Hex] = set()
        raw_legal = payload.get("legal_next_hexes")
        if isinstance(raw_legal, list):
            for row in raw_legal:
                if isinstance(row, dict):
                    try:
                        legal.add(Hex(int(row["i"]), int(row["j"]), int(row["k"])))
                    except (KeyError, TypeError, ValueError):
                        pass
        if legal:
            self.display_mgr.highlight_hexes(legal, cls=tip_cls)

        self._sync_retreat_path_polyline(path_hexes)

        self._refresh_turn_action_dock_actions()

    def confirm_retreat_path(self) -> None:
        prev = getattr(self, "_map_selection_preview", None)
        if not isinstance(prev, dict) or not prev.get("confirm_enabled"):
            return
        commit = prev.get("commit_payload")
        if not isinstance(commit, dict):
            return
        from ...retreat_path import parse_wire_path

        path = parse_wire_path(commit.get("path"))
        if len(path) < 2:
            return
        self.execute_action_request("MoveUnit", dict(commit))
        if len(path) <= 2:
            self.cancel_retreat_path()
            return
        self.retreat_path_committed = path
        self.retreat_path_continue_index = 1
        self.retreat_path_hexes = list(path)
        self._map_selection_preview = None
        self._sync_retreat_path_polyline(list(path))

    def _maybe_continue_retreat_path(self) -> None:
        path = getattr(self, "retreat_path_committed", None)
        if path is None or len(path) < 2:
            return
        idx = int(getattr(self, "retreat_path_continue_index", 1))
        if idx >= len(path) - 1:
            self.retreat_path_committed = None
            self.retreat_path_continue_index = 0
            self.cancel_retreat_path()
            return
        st = self._interactive_game_state()
        uid = str(getattr(self, "retreat_path_unit_id", "") or "").strip()
        if st is None or not uid:
            self.retreat_path_committed = None
            return
        u = st.board.units.get(uid)
        if u is None or u.position != path[idx]:
            return
        self.retreat_path_continue_index = idx + 1
        self.execute_action_request(
            "MoveUnit",
            {
                "unit_id": uid,
                "from_hex": {
                    "i": int(path[idx].i),
                    "j": int(path[idx].j),
                    "k": int(path[idx].k),
                },
                "to_hex": {
                    "i": int(path[idx + 1].i),
                    "j": int(path[idx + 1].j),
                    "k": int(path[idx + 1].k),
                },
            },
        )


__all__ = ["ClientRetreatPathMixin"]
