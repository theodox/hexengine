"""Engine default turn action dock for ``UIHook.TURN_ACTION_DOCK_FOR_VIEWER``."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..arcs.segment_wire import segment_allows_action
from ..authoring.present import panel_action, turn_dock_panel
from ..state import GameState
from ..ui.display import PanelAction, TurnDockPanel


@dataclass(frozen=True, slots=True)
class TurnActionDockContext:
    """
    Inputs for building per-viewer ``StateUpdate.interaction_panels`` dock rows.

    Intentionally has no draft field: map SELECT drafts are client-local until
    commit. Preview hooks consult per snapshot; this hook sees authoritative
    segment + turn state only.
    """

    state: GameState
    viewer_faction: str | None
    session_state_key: str | None
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


def _end_phase_row(ctx: TurnActionDockContext, *, enabled: bool) -> PanelAction:
    su = ctx.shell_ui if isinstance(ctx.shell_ui, Mapping) else {}
    return panel_action(
        id="end_phase",
        action_type="NextPhase",
        label=_shell_ui_label(su, "advance_turn_button_label", "End Phase"),
        title=_shell_ui_label(
            su,
            "advance_turn_button_label",
            "Advance to the next phase in the schedule.",
        ),
        payload={},
        css_class="hexengine-primary-action--end-phase",
        enabled=enabled,
        group="primary",
    )


def _end_phase_enabled(ctx: TurnActionDockContext) -> bool:
    if ctx.current_segment is not None:
        return segment_allows_action(ctx.current_segment, "NextPhase")
    return True


def _presentation_id_for_viewer(ctx: TurnActionDockContext) -> str:
    seg = ctx.current_segment
    if isinstance(seg, dict):
        pid = str(seg.get("presentation_id", "")).strip()
        if pid:
            return pid
    if not ctx.viewer_is_turn_owner:
        return "hidden"
    return "routine"


def empty_turn_action_dock_for_viewer(
    _ctx: TurnActionDockContext,
) -> list[TurnDockPanel]:
    """Minimal dock hook for tests or titles with no commit buttons on ``#user-controls``."""

    return []


def default_turn_action_dock_for_viewer(
    ctx: TurnActionDockContext,
) -> list[TurnDockPanel]:
    """
    Engine catalog default: one ``turn_actions`` panel on host ``user-controls``.

    Adds End Phase when ``NextPhase`` is allowed on ``current_segment``. Combat gate
    rows (Disrupt / Advance / Skip) are title helpers — see
    ``authoring.patterns.combat.combat_gate_panel_actions``.
    """

    if not ctx.viewer_is_turn_owner:
        return []

    actions: list[PanelAction] = []
    presentation_id = _presentation_id_for_viewer(ctx)

    if _end_phase_enabled(ctx):
        actions.append(_end_phase_row(ctx, enabled=True))
    else:
        actions.append(_end_phase_row(ctx, enabled=False))

    if not actions and presentation_id == "routine":
        actions.append(_end_phase_row(ctx, enabled=False))

    return [
        turn_dock_panel(
            presentation_id=presentation_id,
            actions=tuple(actions),
            css_class=f"hexengine-turn-dock hexengine-turn-dock--{presentation_id}",
        )
    ]


__all__ = [
    "TurnActionDockContext",
    "empty_turn_action_dock_for_viewer",
    "default_turn_action_dock_for_viewer",
    "_end_phase_row",
    "_shell_ui_label",
]
