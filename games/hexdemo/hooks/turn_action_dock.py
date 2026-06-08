"""
Hexdemo turn action dock: one commit panel per viewer on host ``user-controls``.

Attack-plan confirm/cancel merge on the client from ``map_selection_preview``.
Rows and End-Phase gating derive from ``current_segment``; copy/HTML from the
segment presentation registry (``segment_ui`` + ``presentation.dock``).
"""

from __future__ import annotations

from hexengine.arcs.segment_wire import (
    action_rows_from_segment,
    segment_allows_action,
)
from hexengine.authoring.present import turn_dock_panel
from hexengine.hooks.ui import TurnActionDockContext, UIHook
from hexengine.hooks.ui_turn_action_dock import _end_phase_row
from hexengine.hooks.wiring import bind_title_hook
from hexengine.ui.display import PanelAction, TurnDockPanel

from ..presentation.dock import dock_headline, dock_panel_html


def _segment_shows_dock(
    presentation_id: str, gate_actions: tuple[PanelAction, ...]
) -> bool:
    """True when the viewer should see a turn dock panel from segment presentation."""

    if gate_actions:
        return True
    pid = str(presentation_id or "").strip()
    return bool(pid) and pid != "hidden"


@bind_title_hook(UIHook.TURN_ACTION_DOCK_FOR_VIEWER)
def turn_action_dock_for_viewer(
    ctx: TurnActionDockContext,
) -> list[TurnDockPanel]:
    seg = ctx.current_segment if isinstance(ctx.current_segment, dict) else None
    gate_actions = action_rows_from_segment(seg, ctx.shell_ui)

    action_rows: list[PanelAction] = list(gate_actions)
    presentation_id = ""
    if seg is not None:
        presentation_id = str(seg.get("presentation_id", "")).strip()
    if not presentation_id:
        presentation_id = "hidden" if not ctx.viewer_is_turn_owner else "routine"

    if not ctx.viewer_is_turn_owner and not _segment_shows_dock(
        presentation_id, gate_actions
    ):
        return []

    end_enabled = segment_allows_action(ctx.current_segment, "NextPhase")
    action_rows.append(_end_phase_row(ctx, enabled=end_enabled))

    su = ctx.shell_ui
    headline = dock_headline(su, presentation_id)
    html = dock_panel_html(su, presentation_id)
    return [
        turn_dock_panel(
            presentation_id=presentation_id,
            actions=tuple(action_rows),
            headline=headline,
            html=html,
            css_class=f"hexdemo-turn-dock hexdemo-turn-dock--{presentation_id}",
        )
    ]


__all__ = ["turn_action_dock_for_viewer"]
