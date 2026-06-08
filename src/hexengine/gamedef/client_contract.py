"""Title-authored client integration manifest (SELECT modes + panel action routes)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

PanelActionMode = Literal["local", "preview_commit"]


def _strip_str(v: Any) -> str | None:
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


@dataclass(frozen=True, slots=True)
class ClientSelectModeRow:
    """One map-selection ``InteractionKind`` wired to client mixin methods."""

    kind: str
    apply_method: str
    draft_active_method: str | None = None
    draft_presentation_id: str | None = None

    def to_wire_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": self.kind,
            "apply_method": self.apply_method,
        }
        if self.draft_active_method:
            out["draft_active_method"] = self.draft_active_method
        if self.draft_presentation_id:
            out["draft_presentation_id"] = self.draft_presentation_id
        return out


@dataclass(frozen=True, slots=True)
class ClientPanelActionRouteRow:
    """One turn-dock / preview button dispatch row for the browser client."""

    mode: PanelActionMode
    method: str | None = None
    wire_action_type: str | None = None
    after_method: str | None = None
    match_action_type: str | None = None
    match_id: str | None = None

    def to_wire_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"mode": self.mode}
        if self.method:
            out["method"] = self.method
        if self.wire_action_type:
            out["wire_action_type"] = self.wire_action_type
        if self.after_method:
            out["after_method"] = self.after_method
        if self.match_action_type:
            out["match_action_type"] = self.match_action_type
        if self.match_id:
            out["match_id"] = self.match_id
        return out


@dataclass(frozen=True, slots=True)
class ClientContractManifest:
    """Declarative client wiring mirrored in ``turn_rules.client_contract``."""

    select_modes: tuple[ClientSelectModeRow, ...] = ()
    panel_action_routes: tuple[ClientPanelActionRouteRow, ...] = ()

    def draft_presentation_id_for_kind(self, kind: str) -> str | None:
        k = str(kind or "").strip()
        for row in self.select_modes:
            if row.kind == k and row.draft_presentation_id:
                return row.draft_presentation_id
        return None

    def to_wire_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"schema": 1}
        if self.select_modes:
            out["select_modes"] = [r.to_wire_dict() for r in self.select_modes]
        if self.panel_action_routes:
            out["panel_action_routes"] = [
                r.to_wire_dict() for r in self.panel_action_routes
            ]
        return out


def client_contract_manifest_from_mapping(data: Any) -> ClientContractManifest | None:
    """Parse ``[client_contract]`` from game data TOML."""
    if not isinstance(data, dict):
        return None
    select_modes = _select_modes_from_rows(data.get("select_modes"))
    routes = _panel_routes_from_rows(data.get("panel_action_routes"))
    if not select_modes and not routes:
        return None
    return ClientContractManifest(
        select_modes=select_modes,
        panel_action_routes=routes,
    )


def client_contract_manifest_from_wire(cc: Mapping[str, Any] | None) -> ClientContractManifest:
    """Parse title manifest rows from ``turn_rules.client_contract`` (features ignored)."""
    if not isinstance(cc, Mapping):
        return ClientContractManifest()
    return ClientContractManifest(
        select_modes=_select_modes_from_rows(cc.get("select_modes")),
        panel_action_routes=_panel_routes_from_rows(cc.get("panel_action_routes")),
    )


def _select_modes_from_rows(raw: Any) -> tuple[ClientSelectModeRow, ...]:
    if not isinstance(raw, list):
        return ()
    out: list[ClientSelectModeRow] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        kind = _strip_str(row.get("kind"))
        apply_method = _strip_str(row.get("apply_method"))
        if not kind or not apply_method:
            continue
        out.append(
            ClientSelectModeRow(
                kind=kind,
                apply_method=apply_method,
                draft_active_method=_strip_str(row.get("draft_active_method")),
                draft_presentation_id=_strip_str(row.get("draft_presentation_id")),
            )
        )
    return tuple(out)


def _panel_routes_from_rows(raw: Any) -> tuple[ClientPanelActionRouteRow, ...]:
    if not isinstance(raw, list):
        return ()
    out: list[ClientPanelActionRouteRow] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        mode_raw = _strip_str(row.get("mode"))
        if mode_raw not in ("local", "preview_commit"):
            continue
        match_id = _strip_str(row.get("match_id"))
        match_action_type = _strip_str(row.get("match_action_type"))
        if not match_id and not match_action_type:
            continue
        out.append(
            ClientPanelActionRouteRow(
                mode=mode_raw,  # type: ignore[arg-type]
                method=_strip_str(row.get("method")),
                wire_action_type=_strip_str(row.get("wire_action_type")),
                after_method=_strip_str(row.get("after_method")),
                match_action_type=match_action_type,
                match_id=match_id,
            )
        )
    return tuple(out)


__all__ = [
    "ClientContractManifest",
    "ClientPanelActionRouteRow",
    "ClientSelectModeRow",
    "PanelActionMode",
    "client_contract_manifest_from_mapping",
    "client_contract_manifest_from_wire",
]
