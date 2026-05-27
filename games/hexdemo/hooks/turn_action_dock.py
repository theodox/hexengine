"""
Hexdemo turn action dock: one commit panel per viewer on host ``advance``.

Attack-plan confirm/cancel merge on the client from ``map_selection_preview``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hexengine.hooks.ui import TurnActionDockContext, UIHook
from hexengine.hooks import ui_primary_actions
from hexengine.hooks.ui_turn_action_dock import (
    _combat_gate_blocks_end_phase,
    _end_phase_row,
    _shell_ui_label,
)
from hexengine.hooks.wiring import bind_title_hook

from ..combat_transitions import dock_arc_hint
from ..ui_markup import render_dock_gate_panel_html


def _gate_actions(ctx: TurnActionDockContext) -> list[dict[str, Any]]:
    from hexengine.hooks.ui_primary_actions import PrimaryActionsContext

    pa_ctx = PrimaryActionsContext(
        state=ctx.state,
        viewer_faction=ctx.viewer_faction,
        extension_key=ctx.extension_key,
        shell_ui=ctx.shell_ui,
    )
    return ui_primary_actions.default_primary_actions_for_viewer(pa_ctx)


def _panel_html(ctx: TurnActionDockContext, dock_arc: str) -> str:
    su = ctx.shell_ui if isinstance(ctx.shell_ui, Mapping) else {}
    if dock_arc in ("retreat_gate", "advance_gate"):
        hint = su.get("dock_gate_panel_hint") if isinstance(su, Mapping) else None
        hint_s = str(hint).strip() if isinstance(hint, str) else ""
        if hint_s:
            return render_dock_gate_panel_html(hint_s)
    return ""


def _headline(ctx: TurnActionDockContext, dock_arc: str) -> str:
    if dock_arc == "hidden":
        return ""
    if dock_arc == "retreat_gate":
        return _shell_ui_label(ctx.shell_ui, "dock_retreat_gate_headline", "Retreat")
    if dock_arc == "advance_gate":
        return _shell_ui_label(ctx.shell_ui, "dock_advance_gate_headline", "Advance")
    if dock_arc == "attack_ready":
        return _shell_ui_label(ctx.shell_ui, "dock_attack_ready_headline", "Combat")
    return _shell_ui_label(ctx.shell_ui, "dock_routine_headline", "Your turn")


@bind_title_hook(UIHook.TURN_ACTION_DOCK_FOR_VIEWER)
def turn_action_dock_for_viewer(
    ctx: TurnActionDockContext,
) -> list[dict[str, Any]]:
    gate_actions = _gate_actions(ctx)
    from .. import combat

    has_retreat_ob = bool(
        ctx.viewer_faction
        and combat.faction_has_pending_retreat(ctx.state, str(ctx.viewer_faction))
    )
    if not ctx.viewer_is_turn_owner and not gate_actions and not has_retreat_ob:
        return []
    actions = [dict(a) for a in gate_actions]
    dock_arc = dock_arc_hint(
        state=ctx.state,
        viewer_faction=ctx.viewer_faction,
        viewer_is_turn_owner=ctx.viewer_is_turn_owner,
        current_phase=ctx.current_phase,
        gate_actions=gate_actions,
    )

    # End Phase stays available in Combat unless a combat_gate blocks it.
    # Client disables end_phase while an attack-plan draft is active (see contract).
    end_enabled = not _combat_gate_blocks_end_phase(ctx)
    actions.append(_end_phase_row(ctx, enabled=end_enabled))

    html = _panel_html(ctx, dock_arc)
    panel: dict[str, Any] = {
        "schema": 1,
        "id": "turn_actions",
        "host": "advance",
        "dock_arc": dock_arc,
        "headline": _headline(ctx, dock_arc),
        "css_class": f"hexdemo-turn-dock hexdemo-turn-dock--{dock_arc}",
        "actions": actions,
        "inputs": [],
    }
    if html:
        panel["html"] = html
    return [panel]


__all__ = ["turn_action_dock_for_viewer"]
