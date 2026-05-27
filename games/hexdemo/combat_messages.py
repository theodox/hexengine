"""Hexdemo combat rows for ``StateUpdate.interaction_messages``."""

from __future__ import annotations

from hexengine.hooks.ui import (
    AdvanceGateInteractionContext,
    CombatInteractionContext,
    ENGINE_DEFAULT,
)
from hexengine.hooks.ui_combat_messages import (
    CombatInteractionMessagesContext,
    default_combat_interaction_messages,
    retreat_owner_faction,
)

from .constants import PACK_STATE_EXTENSION_KEY
from .hooks import ui as ui_hooks


def build_combat_interaction_messages(
    ctx: CombatInteractionMessagesContext,
) -> list[dict[str, object]]:
    """Combat/retreat/advance banner rows using hexdemo UI hook copy."""

    def combat_instruction(outcome: str, retreat_owner: str | None) -> tuple[str, str]:
        cctx = CombatInteractionContext(
            state=ctx.state,
            viewer_faction=ctx.viewer_faction,
            outcome=outcome,
            retreat_owner_faction=retreat_owner,
        )
        raw = ui_hooks.combat_instruction_for_viewer(cctx)
        if raw is ENGINE_DEFAULT:
            from hexengine.hooks.ui import default_combat_instruction_for_viewer

            return default_combat_instruction_for_viewer(cctx)
        return raw  # type: ignore[return-value]

    def advance_gate_banners(advancing_faction: str) -> tuple[str, str]:
        actx = AdvanceGateInteractionContext(
            state=ctx.state,
            viewer_faction=ctx.viewer_faction,
            advancing_faction=advancing_faction,
        )
        raw = ui_hooks.advance_gate_banners_for_viewer(actx)
        if raw is ENGINE_DEFAULT:
            from hexengine.hooks.ui import default_advance_gate_banners_for_viewer

            return default_advance_gate_banners_for_viewer(actx)
        return raw  # type: ignore[return-value]

    ek = str(ctx.extension_key or PACK_STATE_EXTENSION_KEY).strip()
    return default_combat_interaction_messages(
        CombatInteractionMessagesContext(
            state=ctx.state,
            viewer_faction=ctx.viewer_faction,
            extension_key=ek or PACK_STATE_EXTENSION_KEY,
        ),
        combat_instruction=combat_instruction,
        advance_gate_banners=advance_gate_banners,
    )


__all__ = ["build_combat_interaction_messages", "retreat_owner_faction"]
