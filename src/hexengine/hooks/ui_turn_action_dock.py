"""Engine default turn action dock for ``UIHook.TURN_ACTION_DOCK_FOR_VIEWER``."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..arcs.segment_wire import (
    action_rows_from_segment,
    dock_arc_from_segment,
    segment_allows_action,
)
from ..state import GameState


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
    current_segment: dict[str, Any] | None = None


def _shell_ui_label(shell_ui: Mapping[str, Any], key: str, default: str) -> str:
    raw = shell_ui.get(key) if isinstance(shell_ui, Mapping) else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return default


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


def _segment_gate_actions(ctx: TurnActionDockContext) -> list[dict[str, Any]]:
    return action_rows_from_segment(ctx.current_segment, ctx.shell_ui)


def _end_phase_enabled(ctx: TurnActionDockContext) -> bool:
    if ctx.current_segment is not None:
        return segment_allows_action(ctx.current_segment, "NextPhase")
    return True


def _dock_arc_for_viewer(
    ctx: TurnActionDockContext, gate_actions: list[dict[str, Any]]
) -> str:
    if ctx.current_segment is not None:
        return dock_arc_from_segment(
            ctx.current_segment,
            viewer_may_act=ctx.viewer_is_turn_owner,
            current_phase=ctx.current_phase,
            extra_gate_actions=gate_actions,
        )
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


def empty_turn_action_dock_for_viewer(
    _ctx: TurnActionDockContext,
) -> list[dict[str, Any]]:
    """Minimal dock hook for tests or titles with no commit buttons on ``#user-controls``."""

    return []


def default_turn_action_dock_for_viewer(
    ctx: TurnActionDockContext,
) -> list[dict[str, Any]]:
    """
    Engine catalog default: one ``turn_actions`` panel on host ``user-controls``.

    Gate rows derive from ``current_segment.allowed_actions`` when present; End Phase
    is enabled when ``NextPhase`` is in the segment's allowed set.
    """

    gate_actions = _segment_gate_actions(ctx)
    if not ctx.viewer_is_turn_owner and not gate_actions:
        return []

    actions = [dict(a) for a in gate_actions]
    dock_arc = _dock_arc_for_viewer(ctx, gate_actions)

    if _end_phase_enabled(ctx):
        actions.append(_end_phase_row(ctx, enabled=True))
    elif ctx.viewer_is_turn_owner or gate_actions:
        actions.append(_end_phase_row(ctx, enabled=False))

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
    "_end_phase_row",
    "_shell_ui_label",
]
