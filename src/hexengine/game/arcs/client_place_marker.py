"""
Marker relocation via ``place_marker`` map-selection (Shift+click marker, pick hex, Confirm).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...gamedef.interactions import InteractionKind
from ...hexes.types import Hex

if TYPE_CHECKING:
    pass


class ClientPlaceMarkerMixin:
    """Draft state for click-to-confirm marker moves."""

    place_marker_id: str | None
    place_marker_from_hex: Hex | None
    place_marker_to_hex: Hex | None

    def _client_has_place_marker_selection(self) -> bool:
        return InteractionKind.PLACE_MARKER in (
            self._map_selection_preview_handlers().keys()
        )

    def _place_marker_relocate_active(self) -> bool:
        if not self._client_has_place_marker_selection():
            return False
        return bool(str(getattr(self, "place_marker_id", "") or "").strip())

    def cancel_place_marker(self) -> None:
        self.place_marker_id = None
        self.place_marker_from_hex = None
        self.place_marker_to_hex = None
        self._map_selection_preview = None
        self.display_mgr.clear_highlights()
        self._refresh_turn_action_dock_actions()

    def begin_place_marker_relocate(self, marker_id: str) -> None:
        if not self._client_has_place_marker_selection():
            return
        if not self.is_my_turn():
            return
        mid = str(marker_id).strip()
        mgr = getattr(self, "marker_mgr", None)
        if mgr is None or not mgr.has_display(mid):
            return
        disp = mgr.get_display(mid)
        if disp is None:
            return
        if self.ui_state.drag_preview is not None:
            preview = self.ui_state.end_drag()
            self._restore_drag_preview_to_committed(preview)
        self.place_marker_id = mid
        self.place_marker_from_hex = disp.position
        self.place_marker_to_hex = disp.position
        self.ui_state.select_marker(mid)
        mgr.set_marker_hilite(mid)
        self._clear_drag_and_highlights()
        self._request_map_selection_preview(
            InteractionKind.PLACE_MARKER, self._place_marker_draft_wire()
        )

    def set_place_marker_hex(self, h: Hex) -> None:
        if not self._place_marker_relocate_active():
            return
        self.place_marker_to_hex = h
        self._request_map_selection_preview(
            InteractionKind.PLACE_MARKER, self._place_marker_draft_wire()
        )

    def _place_marker_draft_wire(self) -> dict[str, Any]:
        mid = str(getattr(self, "place_marker_id", "") or "").strip()
        draft: dict[str, Any] = {"marker_id": mid}
        h = getattr(self, "place_marker_to_hex", None)
        if isinstance(h, Hex):
            draft["to_hex"] = {"i": int(h.i), "j": int(h.j), "k": int(h.k)}
        return draft

    def _apply_place_marker_preview(self, payload: dict[str, Any]) -> None:
        hi = self._client_title_data().hex_highlights
        cls = (
            hi.marker_hex_class
            if isinstance(hi.marker_hex_class, str) and hi.marker_hex_class.strip()
            else "highlight"
        )
        self.display_mgr.clear_highlights()
        legal: set[Hex] = set()
        raw = payload.get("valid_target_hexes")
        if isinstance(raw, list):
            for row in raw:
                if isinstance(row, dict):
                    try:
                        legal.add(Hex(int(row["i"]), int(row["j"]), int(row["k"])))
                    except (KeyError, TypeError, ValueError):
                        pass
        if legal:
            self.display_mgr.highlight_hexes(legal, cls=cls)

        self._refresh_turn_action_dock_actions()

    def confirm_place_marker(self) -> None:
        prev = getattr(self, "_map_selection_preview", None)
        if not isinstance(prev, dict) or not prev.get("confirm_enabled"):
            return
        commit = prev.get("commit_payload")
        if not isinstance(commit, dict):
            return
        self.execute_action_request("MoveMarker", dict(commit))
        self.cancel_place_marker()
        self.ui_state.select_marker(None)
        mgr = getattr(self, "marker_mgr", None)
        if mgr is not None:
            mgr.set_marker_hilite(None)


__all__ = ["ClientPlaceMarkerMixin"]
