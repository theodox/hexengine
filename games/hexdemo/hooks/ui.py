"""
Hexdemo UI hooks.

Presentation copy lives in ``hexdemo.presentation``; phase/inspect templates in
``hexdemo.ui_markup``.
"""

from __future__ import annotations

from hexengine.hooks.inform_popup import InformPopupContext
from hexengine.hooks.ui import (
    ENGINE_DEFAULT,
    AdvanceGateInteractionContext,
    CombatEventSummary,
    CombatInteractionContext,
    CombatInteractionMessagesContext,
    PhaseBannerContext,
    UIHook,
)
from hexengine.hooks.ui_combat_messages import default_combat_interaction_messages
from hexengine.hooks.wiring import bind_title_hook
from hexengine.state import GameState

from .. import title_state
from ..constants import PACK_STATE_EXTENSION_KEY
from ..presentation.inform import inform_popup_for_profile
from ..presentation.interaction_messages import (
    advance_gate_banners_for_viewer as advance_gate_banner_copy,
)
from ..presentation.interaction_messages import (
    combat_instruction_for_viewer as combat_instruction_copy,
)
from ..ui_markup import (
    phase_banner_label,
    render_phase_banner_html,
    unit_inspect_popup,
)


def _combat_event_summary_from_state(state: GameState) -> CombatEventSummary | None:
    last = title_state.last_combat(state)
    if last is None:
        return None

    retreat_distance = last.get("retreat_distance")
    rd_int: int | None = None
    if isinstance(retreat_distance, int):
        rd_int = retreat_distance
    elif retreat_distance is not None:
        try:
            rd_int = int(retreat_distance)
        except (TypeError, ValueError):
            rd_int = None

    retreat_unit_raw = last.get("retreat_unit_id")
    ru: str | None = str(retreat_unit_raw) if retreat_unit_raw else None

    hex_remaining: int | None = None
    if ru is not None:
        raw_rem = title_state.retreat_obligations(state).get(ru)
        if isinstance(raw_rem, int | float | str):
            try:
                hex_remaining = int(raw_rem)
            except (TypeError, ValueError):
                hex_remaining = None

    return CombatEventSummary(
        attack_kind=str(last.get("attack_kind", "")),
        outcome=str(last.get("outcome", "")),
        attacker_id=str(last.get("attacker_id", "")),
        defender_id=str(last.get("defender_id", "")),
        retreat_distance=rd_int,
        retreat_unit_id=ru,
        retreat_hexes_remaining=hex_remaining,
    )


@bind_title_hook(UIHook.PHASE_BANNER_TEXT_FOR_VIEWER)
def phase_banner_text_for_viewer(ctx: PhaseBannerContext) -> str:
    return phase_banner_label(ctx)


@bind_title_hook(UIHook.PHASE_BANNER_HTML_FOR_VIEWER)
def phase_banner_html_for_viewer(ctx: PhaseBannerContext) -> str:
    return render_phase_banner_html(ctx)


@bind_title_hook(UIHook.COMBAT_INSTRUCTION_FOR_VIEWER)
def combat_instruction_for_viewer(ctx: CombatInteractionContext) -> tuple[str, str]:
    return combat_instruction_copy(ctx, shell_ui=ctx.shell_ui)


@bind_title_hook(UIHook.ADVANCE_GATE_BANNERS_FOR_VIEWER)
def advance_gate_banners_for_viewer(
    ctx: AdvanceGateInteractionContext,
) -> tuple[str, str]:
    return advance_gate_banner_copy(ctx, shell_ui=ctx.shell_ui)


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


@bind_title_hook(UIHook.COMBAT_INTERACTION_MESSAGES)
def combat_interaction_messages(
    ctx: CombatInteractionMessagesContext,
) -> list[dict[str, object]]:
    su = dict(ctx.shell_ui) if ctx.shell_ui else {}

    def combat_instruction(outcome: str, retreat_owner: str | None) -> tuple[str, str]:
        cctx = CombatInteractionContext(
            state=ctx.state,
            viewer_faction=ctx.viewer_faction,
            outcome=outcome,
            retreat_owner_faction=retreat_owner,
            shell_ui=su,
        )
        return combat_instruction_copy(cctx, shell_ui=su)

    def advance_gate_banners(advancing_faction: str) -> tuple[str, str]:
        actx = AdvanceGateInteractionContext(
            state=ctx.state,
            viewer_faction=ctx.viewer_faction,
            advancing_faction=advancing_faction,
            shell_ui=su,
        )
        return advance_gate_banner_copy(actx, shell_ui=su)

    return default_combat_interaction_messages(
        ctx,
        combat_instruction=combat_instruction,
        advance_gate_banners=advance_gate_banners,
    )


@bind_title_hook(UIHook.COMBAT_EVENT_SUMMARY)
def combat_event_summary(state: GameState) -> CombatEventSummary | None:
    return _combat_event_summary_from_state(state)


@bind_title_hook(UIHook.INFORM_POPUP)
def inform_popup_for_viewer(ctx: InformPopupContext):
    if not isinstance(ctx, InformPopupContext):
        from hexengine.authoring.present import inform_popup

        return inform_popup(text="", kind="info", ttl_ms=800)
    profile = str(ctx.inform_profile or ctx.inform_kind or "").strip()
    if profile:
        return inform_popup_for_profile(ctx.shell_ui, profile, ctx.reason)
    return inform_popup_for_profile(ctx.shell_ui, "inform", ctx.reason)


__all__ = [
    "advance_gate_banners_for_viewer",
    "combat_event_summary",
    "combat_interaction_messages",
    "combat_instruction_for_viewer",
    "phase_banner_html_for_viewer",
    "phase_banner_text_for_viewer",
    "popup_message",
    "inform_popup_for_viewer",
]
