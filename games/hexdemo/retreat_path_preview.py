"""Retreat path map-selection preview (click-to-extend, stepwise commit)."""

from __future__ import annotations

from typing import Any

from hexengine.hexes.math import distance
from hexengine.hexes.types import Hex
from hexengine.hooks.core import ENGINE_DEFAULT
from hexengine.hooks.movement import MoveContext, RetreatPathPreviewContext
from hexengine.retreat_path import (
    compute_retreat_path_highlight_sets,
    hex_to_wire,
    hexes_to_wire,
    legal_next_retreat_path_hexes,
    path_from_draft,
    validate_retreat_path,
)
from hexengine.state import GameState

from . import combat
from .hooks import movement as movement_hooks


def _shell_label(shell_ui: dict[str, Any], key: str, default: str) -> str:
    raw = shell_ui.get(key) if isinstance(shell_ui, dict) else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return default


def _panel_actions(shell_ui: dict[str, Any], *, confirm_enabled: bool) -> list[dict[str, Any]]:
    return [
        {
            "schema": 1,
            "id": "retreat_path_confirm",
            "action_type": "MoveUnit",
            "label": _shell_label(shell_ui, "retreat_path_confirm_label", "Confirm retreat"),
            "title": _shell_label(
                shell_ui,
                "retreat_path_confirm_title",
                "Commit the retreat path and move step by step.",
            ),
            "payload": {},
            "css_class": "hexengine-primary-action--confirm",
            "enabled": confirm_enabled,
            "group": "primary",
        },
        {
            "schema": 1,
            "id": "retreat_path_undo",
            "action_type": "RetreatPathUndo",
            "label": _shell_label(shell_ui, "retreat_path_undo_label", "Undo hex"),
            "title": "Remove the last hex from the path.",
            "payload": {},
            "css_class": "hexengine-primary-action--secondary",
            "enabled": True,
            "group": "secondary",
        },
        {
            "schema": 1,
            "id": "retreat_path_cancel",
            "action_type": "RetreatPathCancel",
            "label": _shell_label(shell_ui, "retreat_path_cancel_label", "Cancel"),
            "title": "Clear the retreat path draft.",
            "payload": {},
            "css_class": "hexengine-primary-action--cancel",
            "enabled": True,
            "group": "secondary",
        },
    ]


def retreat_path_preview(ctx: RetreatPathPreviewContext) -> dict[str, Any]:
    st = ctx.state
    faction = str(ctx.player_faction).strip()
    su = ctx.shell_ui if isinstance(ctx.shell_ui, dict) else {}
    draft = ctx.draft if isinstance(ctx.draft, dict) else {}

    uid = str(draft.get("unit_id", "")).strip()
    if not uid:
        return {
            "kind": "retreat_path",
            "status_text": _shell_label(
                su, "retreat_path_pick_unit_status", "Select a unit that must retreat."
            ),
            "confirm_enabled": False,
            "legal_next_hexes": [],
            "preview_path_hexes": [],
            "panel_actions": _panel_actions(su, confirm_enabled=False),
        }

    unit = st.board.units.get(uid)
    if unit is None or not unit.active or str(unit.faction).strip() != faction:
        return {
            "kind": "retreat_path",
            "status_text": "That unit is not yours.",
            "confirm_enabled": False,
            "legal_next_hexes": [],
            "preview_path_hexes": [],
            "panel_actions": _panel_actions(su, confirm_enabled=False),
        }

    rem = combat.retreat_hexes_remaining(st, uid)
    if rem is None:
        return {
            "kind": "retreat_path",
            "status_text": "This unit has no retreat obligation.",
            "confirm_enabled": False,
            "legal_next_hexes": [],
            "preview_path_hexes": [],
            "panel_actions": _panel_actions(su, confirm_enabled=False),
        }

    path = path_from_draft(draft)
    start = unit.position
    if not path:
        path = (start,)
    elif path[0] != start:
        path = (start, *path)

    blocked = movement_hooks.retreat_blocked_hexes(st, uid)
    if blocked is ENGINE_DEFAULT:
        blocked_set = None
    else:
        blocked_set = blocked if isinstance(blocked, frozenset) else frozenset(blocked)

    def step_fn(
        state: GameState, from_hex: Hex, to_hex: Hex, base_cost: float
    ) -> float:
        return float(
            movement_hooks.movement_step_cost_for_unit(
                state, uid, from_hex, to_hex, base_cost
            )
        )

    max_stack = 3  # matches games/hexdemo/resources/game_data.toml

    through, end = compute_retreat_path_highlight_sets(
        state=st,
        unit_id=uid,
        obligation=int(rem),
        player_faction=faction,
        blocked_hexes=blocked_set,
        max_active_units_per_hex=max_stack,
        step_cost=step_fn,
    )

    legal = legal_next_retreat_path_hexes(
        state=st,
        unit_id=uid,
        path=path,
        obligation=int(rem),
        player_faction=faction,
        blocked_hexes=blocked_set,
        max_active_units_per_hex=max_stack,
        step_cost=step_fn,
    )

    confirm = False
    commit: dict[str, Any] | None = None
    steps_done = len(path) - 1
    dest_ready = len(path) >= 2 and distance(start, path[-1]) == int(rem)
    if dest_ready and (steps_done == int(rem) or len(path) == 2):
        try:

            def _validate_endpoint(
                state: GameState,
                unit_id: str,
                from_hex: Hex,
                to_hex: Hex,
                hexes_remaining: int,
            ) -> None:
                mctx = MoveContext(
                    state=state,
                    unit_id=unit_id,
                    from_hex=from_hex,
                    to_hex=to_hex,
                    player_faction=faction,
                    is_retreat_fulfillment=True,
                )
                movement_hooks.validate_retreat_move(mctx, hexes_remaining)

            validate_retreat_path(
                state=st,
                unit_id=uid,
                path=path,
                obligation=int(rem),
                blocked_hexes=blocked_set,
                max_active_units_per_hex=max_stack,
                step_cost=step_fn,
                validate_endpoint=_validate_endpoint,
            )
            confirm = True
            commit = {
                "unit_id": uid,
                "from_hex": hex_to_wire(path[0]),
                "to_hex": hex_to_wire(path[-1]),
                "path": hexes_to_wire(list(path)),
            }
        except ValueError:
            confirm = False

    if dest_ready:
        status = _shell_label(
            su,
            "retreat_path_ready_status",
            "Retreat path complete — confirm or undo.",
        )
    else:
        status = _shell_label(
            su,
            "retreat_path_pick_hex_status",
            f"Retreat: pick a destination ({int(rem)} hexes away) or extend the path.",
        )

    return {
        "kind": "retreat_path",
        "status_text": status,
        "confirm_enabled": confirm,
        "legal_next_hexes": hexes_to_wire(legal),
        "through_hexes": hexes_to_wire(sorted(through, key=lambda h: (h.i, h.j, h.k))),
        "preview_path_hexes": hexes_to_wire(list(path)),
        "commit_payload": commit,
        "panel_actions": _panel_actions(su, confirm_enabled=confirm),
    }


__all__ = ["retreat_path_preview"]
