"""Typed read model for `StateUpdate.turn_rules` fields owned by title `GameData`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


def _strip_str(v: Any) -> str | None:
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


@dataclass(frozen=True, slots=True)
class FactionUiRow:
    """One faction row from `turn_rules.faction_ui.factions`."""

    id: str
    label: str | None
    css_class: str | None


@dataclass(frozen=True, slots=True)
class ClientFactionUi:
    """Subset of `turn_rules.faction_ui` used for labels and title CSS injection."""

    rows: tuple[FactionUiRow, ...]
    css_inline: str | None
    css_href: str | None

    def row_for(self, faction_id: str) -> FactionUiRow | None:
        fid = str(faction_id)
        for r in self.rows:
            if r.id == fid:
                return r
        return None


@dataclass(frozen=True, slots=True)
class ClientHexHighlightUi:
    """`turn_rules.ui` highlight classes (move / retreat / marker previews)."""

    move_hex_class: str | None = None
    retreat_hex_class: str | None = None
    retreat_through_hex_class: str | None = None
    marker_hex_class: str | None = None

    @staticmethod
    def from_ui_dict(ui: Any) -> ClientHexHighlightUi:
        if not isinstance(ui, dict):
            return ClientHexHighlightUi()
        return ClientHexHighlightUi(
            move_hex_class=_strip_str(ui.get("move_hex_class")),
            retreat_hex_class=_strip_str(ui.get("retreat_hex_class")),
            retreat_through_hex_class=_strip_str(ui.get("retreat_through_hex_class")),
            marker_hex_class=_strip_str(ui.get("marker_hex_class")),
        )


@dataclass(frozen=True, slots=True)
class ClientTitleData:
    """
    Thin-client view of title declarative data carried in `StateUpdate.turn_rules`.

    Parses only the fields the server mirrors from `GameData` (plus
    `client_contract` feature flags and optional `faction_display_contract_error`).
    Schedule entries, movement_budget scalar,
    and rota metadata stay on the raw dict for `_game_definition_from_turn_rules_wire`.
    """

    max_active_units_per_hex: int | None
    movement_budget_attribute_key: str | None
    title_state_extension_key: str | None
    hex_highlights: ClientHexHighlightUi
    faction_ui: ClientFactionUi | None
    faction_display_contract_error: str | None
    client_contract_features: frozenset[str]

    @staticmethod
    def empty() -> ClientTitleData:
        return ClientTitleData(
            max_active_units_per_hex=None,
            movement_budget_attribute_key=None,
            title_state_extension_key=None,
            hex_highlights=ClientHexHighlightUi(),
            faction_ui=None,
            faction_display_contract_error=None,
            client_contract_features=frozenset(),
        )

    @staticmethod
    def from_turn_rules(wire: Mapping[str, Any] | None) -> ClientTitleData:
        if not isinstance(wire, Mapping):
            return ClientTitleData.empty()

        raw_mx = wire.get("max_active_units_per_hex")
        max_stack: int | None = None
        try:
            n = int(raw_mx)
        except (TypeError, ValueError):
            n = 0
        if n > 0:
            max_stack = n

        mv_key = _strip_str(wire.get("movement_budget_attribute"))
        title_key = _strip_str(wire.get("title_state_extension_key"))

        ui_raw = wire.get("ui")
        hex_highlights = ClientHexHighlightUi.from_ui_dict(ui_raw)

        fd_err_raw = wire.get("faction_display_contract_error")
        fd_err: str | None = None
        if isinstance(fd_err_raw, dict):
            fd_err = _strip_str(fd_err_raw.get("text"))
        elif isinstance(fd_err_raw, str):
            fd_err = _strip_str(fd_err_raw)

        fu_raw = wire.get("faction_ui")
        faction_ui: ClientFactionUi | None = None
        if isinstance(fu_raw, dict):
            rows_out: list[FactionUiRow] = []
            facs = fu_raw.get("factions")
            if isinstance(facs, list):
                for row in facs:
                    if not isinstance(row, dict):
                        continue
                    rid = _strip_str(row.get("id"))
                    if rid is None:
                        continue
                    rows_out.append(
                        FactionUiRow(
                            id=rid,
                            label=_strip_str(row.get("label")),
                            css_class=_strip_str(row.get("css_class")),
                        )
                    )
            css_inline = _strip_str(fu_raw.get("css"))
            css_href = _strip_str(fu_raw.get("css_href"))
            if rows_out or css_inline is not None or css_href is not None:
                faction_ui = ClientFactionUi(
                    rows=tuple(rows_out),
                    css_inline=css_inline,
                    css_href=css_href,
                )

        cc = wire.get("client_contract")
        feats: frozenset[str] = frozenset()
        if isinstance(cc, dict):
            raw_feats = cc.get("features")
            if isinstance(raw_feats, list):
                feats = frozenset(
                    str(x).strip()
                    for x in raw_feats
                    if isinstance(x, str) and str(x).strip()
                )

        return ClientTitleData(
            max_active_units_per_hex=max_stack,
            movement_budget_attribute_key=mv_key,
            title_state_extension_key=title_key,
            hex_highlights=hex_highlights,
            faction_ui=faction_ui,
            faction_display_contract_error=fd_err,
            client_contract_features=feats,
        )


__all__ = [
    "ClientFactionUi",
    "ClientHexHighlightUi",
    "ClientTitleData",
    "FactionUiRow",
]
