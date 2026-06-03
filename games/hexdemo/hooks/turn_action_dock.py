"""
Hexdemo turn action dock: one commit panel per viewer on host ``advance``.

Attack-plan confirm/cancel merge on the client from ``map_selection_preview``.
Rows and End-Phase gating derive from ``current_segment``; copy/HTML from the
segment presentation registry (``segment_ui`` + ``presentation.dock``).
"""

from __future__ import annotations

from hexengine.arcs.segment_wire import (
    action_rows_from_segment,
    segment_allows_action,
)
from hexengine.authoring.present import panel_actions_from_dicts, turn_dock_panel
from hexengine.hooks.ui import TurnActionDockContext, UIHook
from hexengine.hooks.ui_turn_action_dock import _end_phase_row
from hexengine.hooks.wiring import bind_title_hook
from hexengine.ui.display import TurnDockPanel

from .. import combat
from ..presentation.dock import dock_headline, dock_panel_html
from ..segment_ui import resolve_presentation_id


@bind_title_hook(UIHook.TURN_ACTION_DOCK_FOR_VIEWER)
def turn_action_dock_for_viewer(
    ctx: TurnActionDockContext,
) -> list[TurnDockPanel]:
    gate_actions = action_rows_from_segment(ctx.current_segment, ctx.shell_ui)

    has_retreat_ob = bool(
        ctx.viewer_faction
        and combat.faction_has_pending_retreat(ctx.state, str(ctx.viewer_faction))
    )
    if not ctx.viewer_is_turn_owner and not gate_actions and not has_retreat_ob:
        return []

    action_rows: list[dict] = [dict(a) for a in gate_actions]
    seg = ctx.current_segment if isinstance(ctx.current_segment, dict) else None
    presentation_id = ""
    if seg is not None:
        presentation_id = str(seg.get("presentation_id", "")).strip()
    if not presentation_id:
        presentation_id = resolve_presentation_id(
            seg,
            viewer_may_act=ctx.viewer_is_turn_owner,
            current_phase=ctx.current_phase,
            extra_gate_actions=gate_actions,
        )
    if presentation_id == "hidden" and has_retreat_ob:
        presentation_id = "retreat_gate"

    end_enabled = segment_allows_action(ctx.current_segment, "NextPhase")
    action_rows.append(_end_phase_row(ctx, enabled=end_enabled))

    su = ctx.shell_ui
    headline = dock_headline(su, presentation_id)
    html = dock_panel_html(su, presentation_id)
    return [
        turn_dock_panel(
            presentation_id=presentation_id,
            actions=panel_actions_from_dicts(action_rows),
            host="advance",
            headline=headline,
            html=html,
            css_class=f"hexdemo-turn-dock hexdemo-turn-dock--{presentation_id}",
        )
    ]


__all__ = ["turn_action_dock_for_viewer"]
