"""Marker relocate map-selection preview (click hex + Confirm on dock)."""

from __future__ import annotations

from typing import Any

from hexengine.authoring.present import map_selection_preview, panel_action
from hexengine.hexes.types import Hex, HexColRow
from hexengine.hooks.ui import PlaceMarkerPreviewContext
from hexengine.state.marker_placement import marker_destination_hexes_for_preview
from hexengine.ui.display import MapSelectionPreview, PanelAction

from ..marker_rules import default_marker_placement_rule


def _shell_label(shell_ui: dict[str, Any], key: str, default: str) -> str:
    raw = shell_ui.get(key) if isinstance(shell_ui, dict) else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return default


def _marker_by_id(
    markers: tuple[dict[str, Any], ...], mid: str
) -> dict[str, Any] | None:
    for row in markers:
        if str(row.get("id", "")).strip() == mid:
            return row
    return None


def _position_hex(row: dict[str, Any]) -> Hex | None:
    pos = row.get("position")
    if not isinstance(pos, list | tuple) or len(pos) != 2:
        return None
    try:
        return Hex.from_hex_col_row(HexColRow(col=int(pos[0]), row=int(pos[1])))
    except (TypeError, ValueError):
        return None


def _hex_wire(h: Hex) -> dict[str, int]:
    return {"i": int(h.i), "j": int(h.j), "k": int(h.k)}


def _parse_hex_wire(raw: Any) -> Hex | None:
    if not isinstance(raw, dict):
        return None
    if "col" in raw and "row" in raw:
        try:
            return Hex.from_hex_col_row(
                HexColRow(col=int(raw["col"]), row=int(raw["row"]))
            )
        except (KeyError, TypeError, ValueError):
            return None
    try:
        return Hex(int(raw["i"]), int(raw["j"]), int(raw["k"]))
    except (KeyError, TypeError, ValueError):
        return None


def _panel_actions(
    shell_ui: dict[str, Any], *, confirm_enabled: bool
) -> tuple[PanelAction, ...]:
    return (
        panel_action(
            id="place_marker_confirm",
            action_type="MoveMarker",
            label=_shell_label(shell_ui, "place_marker_confirm_label", "Confirm move"),
            title=_shell_label(
                shell_ui,
                "place_marker_confirm_title",
                "Move the marker to the selected hex.",
            ),
            payload={},
            css_class="hexengine-primary-action--confirm",
            enabled=confirm_enabled,
            group="primary",
        ),
        panel_action(
            id="place_marker_cancel",
            action_type="PlaceMarkerCancel",
            label=_shell_label(shell_ui, "place_marker_cancel_label", "Cancel"),
            title="Cancel marker relocation.",
            payload={},
            css_class="hexengine-primary-action--cancel",
            enabled=True,
            group="secondary",
        ),
    )


def place_marker_preview(ctx: PlaceMarkerPreviewContext) -> MapSelectionPreview:
    if not isinstance(ctx, PlaceMarkerPreviewContext):
        return map_selection_preview(
            kind="place_marker",
            status_text="",
            confirm_enabled=False,
        )

    st = ctx.state
    su = ctx.shell_ui if isinstance(ctx.shell_ui, dict) else {}
    draft = ctx.draft if isinstance(ctx.draft, dict) else {}
    mid = str(draft.get("marker_id", "")).strip()
    if not mid:
        return map_selection_preview(
            kind="place_marker",
            status_text=_shell_label(
                su, "place_marker_pick_marker_status", "Select a marker to relocate."
            ),
            confirm_enabled=False,
            valid_target_hexes=[],
            panel_actions=_panel_actions(su, confirm_enabled=False),
        )

    row = _marker_by_id(ctx.markers, mid)
    if row is None:
        return map_selection_preview(
            kind="place_marker",
            status_text="Unknown marker.",
            confirm_enabled=False,
            valid_target_hexes=[],
            panel_actions=_panel_actions(su, confirm_enabled=False),
        )

    from_hex = _position_hex(row)
    if from_hex is None:
        return map_selection_preview(
            kind="place_marker",
            status_text="Marker has no valid position.",
            confirm_enabled=False,
            valid_target_hexes=[],
            panel_actions=_panel_actions(su, confirm_enabled=False),
        )

    rule = default_marker_placement_rule()
    legal = marker_destination_hexes_for_preview(st, row, rule)
    legal_wire = [_hex_wire(h) for h in sorted(legal, key=lambda x: (x.i, x.j, x.k))]

    to_hex = _parse_hex_wire(draft.get("to_hex"))
    if to_hex is None:
        to_hex = from_hex

    confirm = to_hex in legal and to_hex != from_hex
    commit: dict[str, Any] | None = None
    if confirm:
        fc = HexColRow.from_hex(from_hex)
        tc = HexColRow.from_hex(to_hex)
        commit = {
            "marker_id": mid,
            "from_position": [int(fc.col), int(fc.row)],
            "to_position": [int(tc.col), int(tc.row)],
        }

    if to_hex == from_hex:
        status = _shell_label(
            su,
            "place_marker_pick_hex_status",
            "Shift+click a marker, then click a destination hex.",
        )
    elif confirm:
        status = _shell_label(
            su,
            "place_marker_ready_status",
            "Destination set — confirm or pick another hex.",
        )
    else:
        status = _shell_label(
            su,
            "place_marker_invalid_status",
            "That hex is not a legal marker destination.",
        )

    return map_selection_preview(
        kind="place_marker",
        status_text=status,
        confirm_enabled=confirm,
        valid_target_hexes=legal_wire,
        preview_path_hexes=[_hex_wire(from_hex)]
        + ([_hex_wire(to_hex)] if to_hex != from_hex else []),
        commit_payload=commit,
        panel_actions=_panel_actions(su, confirm_enabled=confirm),
    )


__all__ = ["place_marker_preview"]
