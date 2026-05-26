"""
Hexdemo UI hooks.

Thin adapters over ``hexdemo.ui_markup`` templates and copy constants.
"""

from __future__ import annotations

from hexengine.hooks.ui import (
    AdvanceGateInteractionContext,
    CombatInteractionContext,
    ENGINE_DEFAULT,
    PhaseBannerContext,
    UIHook,
)
from hexengine.hooks.wiring import bind_title_hook
from hexengine.state import GameState

from ..inform_popups import inform_popup
from ..ui_markup import (
    phase_banner_label,
    render_phase_banner_html,
    unit_inspect_popup,
)


@bind_title_hook(UIHook.PHASE_BANNER_TEXT_FOR_VIEWER)
def phase_banner_text_for_viewer(ctx: PhaseBannerContext) -> str:
    return phase_banner_label(ctx)


@bind_title_hook(UIHook.PHASE_BANNER_HTML_FOR_VIEWER)
def phase_banner_html_for_viewer(ctx: PhaseBannerContext) -> str:
    return render_phase_banner_html(ctx)


@bind_title_hook(UIHook.COMBAT_INSTRUCTION_FOR_VIEWER)
def combat_instruction_for_viewer(
    ctx: CombatInteractionContext,
) -> tuple[str, str]:
    recipient = str(ctx.viewer_faction).strip() if ctx.viewer_faction else ""
    outcome = ctx.outcome
    retreat_owner = ctx.retreat_owner_faction

    match (outcome, retreat_owner, recipient):
        case ("defender_destroyed", _, _):
            return "resolved", "Defender destroyed."
        case ("none", _, _):
            return "resolved", "Combat resolved with no effect."
        case (_, None, _):
            return "resolved", "Combat resolved."
        case (_, ro, rec) if rec == ro:
            return (
                "retreat_required",
                "Mandatory retreat: move the unit one hex (exact distance).",
            )
        case _:
            return (
                "wait",
                "Hold — waiting for the opponent's mandatory retreat.",
            )


@bind_title_hook(UIHook.ADVANCE_GATE_BANNERS_FOR_VIEWER)
def advance_gate_banners_for_viewer(
    _ctx: AdvanceGateInteractionContext,
) -> tuple[str, str]:
    return (
        "You may advance (click Advance).",
        "Waiting for the opponent to advance.",
    )


@bind_title_hook(UIHook.POPUP_MESSAGE)
def popup_message(
    state: GameState,
    viewer_faction: str | None,
    target_kind: str,
    target_id: str,
) -> dict[str, object] | object:
    tk = str(target_kind)
    tid = str(target_id)

    if tk == "unit":
        return unit_inspect_popup(state, viewer_faction, tid)

    if tk == "marker":
        return {"text": f"marker {tid}", "kind": "info", "ttl_ms": 1200}

    return ENGINE_DEFAULT


@bind_title_hook(UIHook.INFORM_POPUP)
def inform_popup_for_viewer(ctx):
    from hexengine.hooks.inform_popup import InformPopupContext

    if not isinstance(ctx, InformPopupContext):
        return {"text": "", "kind": "info", "ttl_ms": 800}
    return inform_popup(ctx)


__all__ = [
    "advance_gate_banners_for_viewer",
    "combat_instruction_for_viewer",
    "phase_banner_html_for_viewer",
    "phase_banner_text_for_viewer",
    "popup_message",
    "inform_popup_for_viewer",
]
