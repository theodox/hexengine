"""Engine default turn action dock for ``UIHook.TURN_ACTION_DOCK_FOR_VIEWER``."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..state import GameState
from .ui_primary_actions import (
    PrimaryActionsContext,
    default_primary_actions_for_viewer,
)


@dataclass(frozen=True, slots=True)
class TurnActionDockContext:
    """Inputs for building per-viewer ``StateUpdate.interaction_panels`` dock rows."""

    state: GameState
    viewer_faction: str | None
    extension_key: str | None
    shell_ui: Mapping[str, Any]
    schedule_index: int
    current_faction: str
    current_phase: str
    phase_actions_remaining: int
    viewer_is_turn_owner: bool
    client_contract_features: frozenset[str]


def _shell_ui_label(shell_ui: Mapping[str, Any], key: str, default: str) -> str:
    raw = shell_ui.get(key) if isinstance(shell_ui, Mapping) else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return default


def _combat_gate_blocks_end_phase(ctx: TurnActionDockContext) -> bool:
    ek = str(ctx.extension_key).strip() if ctx.extension_key else ""
    if not ek:
        return False
    hx = ctx.state.extension.get(ek)
    if not isinstance(hx, dict):
        return False
    gate = str(hx.get("combat_gate", "")).strip()
    return gate in ("awaiting_retreat_or_disrupt", "awaiting_advance")


def _catalog_gate_actions(ctx: TurnActionDockContext) -> list[dict[str, Any]]:
    pa_ctx = PrimaryActionsContext(
        state=ctx.state,
        viewer_faction=ctx.viewer_faction,
        extension_key=ctx.extension_key,
        shell_ui=ctx.shell_ui,
    )
    return default_primary_actions_for_viewer(pa_ctx)


def _end_phase_row(ctx: TurnActionDockContext, *, enabled: bool) -> dict[str, Any]:
    su = ctx.shell_ui if isinstance(ctx.shell_ui, Mapping) else {}
    return {
        "schema": 1,
        "id": "end_phase",
        "action_type": "NextPhase",
        "label": _shell_ui_label(su, "advance_turn_button_label", "End Phase"),
        "title": _shell_ui_label(
            su,
            "advance_turn_button_label",
            "Advance to the next phase in the schedule.",
        ),
        "payload": {},
        "css_class": "hexengine-primary-action--end-phase",
        "enabled": enabled,
        "group": "primary",
    }


def _dock_arc_for_viewer(ctx: TurnActionDockContext, gate_actions: list[dict[str, Any]]) -> str:
    if not ctx.viewer_is_turn_owner:
        return "hidden"
    if gate_actions:
        for row in gate_actions:
            at = str(row.get("action_type", "")).strip()
            if at == "CombatDisruptInsteadOfRetreat":
                return "retreat_gate"
            if at == "CombatAdvance":
                return "advance_gate"
    return "routine"


def empty_turn_action_dock_for_viewer(_ctx: TurnActionDockContext) -> list[dict[str, Any]]:
    """Minimal dock hook for tests or titles with no commit buttons on ``#user-controls``."""

    return []


def default_turn_action_dock_for_viewer(
    ctx: TurnActionDockContext,
) -> list[dict[str, Any]]:
    """
    Engine catalog default: one ``turn_actions`` panel on host ``user-controls``.

    Gate rows come from the primary-actions catalog; ``end_phase`` is appended when
    the viewer owns the turn and combat gates do not block phase advance.
    """

    if not ctx.viewer_is_turn_owner:
        return []

    gate_actions = _catalog_gate_actions(ctx)
    actions = [dict(a) for a in gate_actions]
    dock_arc = _dock_arc_for_viewer(ctx, gate_actions)

    if not _combat_gate_blocks_end_phase(ctx):
        actions.append(_end_phase_row(ctx, enabled=True))

    if not actions and dock_arc == "routine":
        actions.append(_end_phase_row(ctx, enabled=False))

    return [
        {
            "schema": 1,
            "id": "turn_actions",
            "host": "user-controls",
            "dock_arc": dock_arc,
            "css_class": f"hexengine-turn-dock hexengine-turn-dock--{dock_arc}",
            "actions": actions,
            "inputs": [],
        }
    ]


__all__ = [
    "TurnActionDockContext",
    "empty_turn_action_dock_for_viewer",
    "default_turn_action_dock_for_viewer",
    "_combat_gate_blocks_end_phase",
    "_end_phase_row",
    "_shell_ui_label",
]
