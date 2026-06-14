"""
Map-selection preview client (client-local draft → server consult → ratify on dock).

The client owns draft input; each change sends a snapshot via
``map_selection_preview_request``. Preview responses are consult-only until
commit. Kinds are routed through a small handler table; attack plan is the
reference implementation.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ...gamedef.interactions import InteractionKind
from .client_map_selection_registry import map_selection_preview_handlers

if TYPE_CHECKING:
    pass

PreviewHandler = Callable[[dict[str, Any]], None]


class ClientMapSelectionMixin:
    """Preview RPC + ``panel_actions`` merge on the turn action dock."""

    _map_selection_preview: dict[str, Any] | None
    _map_selection_preview_request_id: str
    _map_selection_preview_pending: bool

    def _map_selection_preview_handlers(self) -> dict[str, PreviewHandler]:
        return map_selection_preview_handlers(self)

    def _client_has_map_selection_previews(self) -> bool:
        return (
            "map_selection_previews"
            in self._client_title_data().client_contract_features
        )

    def _request_map_selection_preview(self, kind: str, draft: dict[str, Any]) -> None:
        if not self._client_has_map_selection_previews():
            return
        client = getattr(self, "client", None)
        if client is None or not client.is_connected():
            return
        self._map_selection_preview_pending = True
        self._map_selection_preview_request_id = uuid.uuid4().hex
        client.send_map_selection_preview_request(
            str(kind).strip(),
            dict(draft),
            request_id=self._map_selection_preview_request_id,
        )

    def _request_attack_plan_preview(self) -> None:
        if not self._client_has_attack_planning_ui():
            return
        self._request_map_selection_preview(
            InteractionKind.ATTACK_PLAN,
            self._attack_plan_draft_wire(),
        )

    def _attack_plan_draft_wire(self) -> dict[str, Any]:
        draft: dict[str, Any] = {"attacker_ids": sorted(self.attack_plan_attacker_ids)}
        if self.attack_plan_target_hex is not None:
            h = self.attack_plan_target_hex
            draft["target_hex"] = {"i": int(h.i), "j": int(h.j), "k": int(h.k)}
        return draft

    def _handle_map_selection_preview(self, payload: dict[str, Any]) -> None:
        rid = str(payload.get("request_id", "") or "")
        if (
            rid
            and self._map_selection_preview_request_id
            and rid != self._map_selection_preview_request_id
        ):
            return
        self._map_selection_preview_pending = False
        self._map_selection_preview = dict(payload)
        kind = str(payload.get("kind", "")).strip()
        handler = self._map_selection_preview_handlers().get(kind)
        if handler is not None:
            handler(payload)

    def _apply_attack_plan_preview(self, payload: dict[str, Any]) -> None:
        self._sync_attack_plan_ui()
        self._refresh_turn_action_dock_actions()

    def _attack_plan_preview_status(self) -> str:
        prev = getattr(self, "_map_selection_preview", None)
        if isinstance(prev, dict):
            raw = prev.get("status_text")
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return self._shell_attack_copy(
            "attack_pick_target_status", ""
        )

    def _attack_plan_confirm_enabled(self) -> bool:
        prev = getattr(self, "_map_selection_preview", None)
        if isinstance(prev, dict):
            return bool(prev.get("confirm_enabled", False))
        return False

    def _attack_plan_eligible_attacker_ids(self) -> set[str]:
        prev = getattr(self, "_map_selection_preview", None)
        if not isinstance(prev, dict):
            return set()
        raw = prev.get("eligible_attacker_ids")
        if not isinstance(raw, list):
            return set()
        return {str(x).strip() for x in raw if str(x).strip()}

    def _attack_plan_valid_target_hexes(self) -> set[tuple[int, int, int]]:
        prev = getattr(self, "_map_selection_preview", None)
        if not isinstance(prev, dict):
            return set()
        raw = prev.get("valid_target_hexes")
        if not isinstance(raw, list):
            return set()
        out: set[tuple[int, int, int]] = set()
        for row in raw:
            if not isinstance(row, dict):
                continue
            try:
                out.add((int(row["i"]), int(row["j"]), int(row["k"])))
            except (KeyError, TypeError, ValueError):
                continue
        return out


__all__ = ["ClientMapSelectionMixin"]
