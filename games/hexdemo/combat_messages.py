"""Hexdemo combat rows for ``StateUpdate.interaction_messages``."""

from __future__ import annotations

from hexengine.hooks.ui import (
    AdvanceGateInteractionContext,
    CombatEventSummary,
    CombatInteractionContext,
    ENGINE_DEFAULT,
)
from hexengine.hooks.ui_combat_messages import (
    CombatInteractionMessagesContext,
    default_combat_interaction_messages,
    retreat_owner_faction,
)
from hexengine.state import GameState
from hexengine.state.title_extension import title_bucket

from .constants import PACK_STATE_EXTENSION_KEY
from .hooks import ui as ui_hooks


def build_combat_event_summary(state: GameState) -> CombatEventSummary | None:
    """Extract the latest combat result from the hexdemo bucket for `combat_event` wires."""

    hx = title_bucket(state, PACK_STATE_EXTENSION_KEY)
    last_combat = hx.get("last_combat") if isinstance(hx, dict) else None
    if not isinstance(last_combat, dict):
        return None

    retreat_distance = last_combat.get("retreat_distance")
    rd_int: int | None = None
    if isinstance(retreat_distance, int):
        rd_int = retreat_distance
    elif retreat_distance is not None:
        try:
            rd_int = int(retreat_distance)
        except (TypeError, ValueError):
            rd_int = None

    retreat_unit_raw = last_combat.get("retreat_unit_id")
    ru: str | None = str(retreat_unit_raw) if retreat_unit_raw else None

    ob = hx.get("retreat_obligations")
    ob = ob if isinstance(ob, dict) else {}
    hex_remaining: int | None = None
    if ru is not None:
        raw_rem = ob.get(ru)
        if isinstance(raw_rem, int | float | str):
            try:
                hex_remaining = int(raw_rem)
            except (TypeError, ValueError):
                hex_remaining = None

    return CombatEventSummary(
        attack_kind=str(last_combat.get("attack_kind", "")),
        outcome=str(last_combat.get("outcome", "")),
        attacker_id=str(last_combat.get("attacker_id", "")),
        defender_id=str(last_combat.get("defender_id", "")),
        retreat_distance=rd_int,
        retreat_unit_id=ru,
        retreat_hexes_remaining=hex_remaining,
    )


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


__all__ = [
    "build_combat_event_summary",
    "build_combat_interaction_messages",
    "retreat_owner_faction",
]
