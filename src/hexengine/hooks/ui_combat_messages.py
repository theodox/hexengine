"""Combat-related interaction message rows (segment-aware, no gate-string reads)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from ..arcs.segment_wire import KIND_DOCK_ARC_ADVANCE, KIND_DOCK_ARC_RETREAT
from ..state import GameState
from ..state.title_extension import title_bucket


def retreat_owner_faction(
    state: GameState, outcome: str, attacker_id: str, defender_id: str
) -> str | None:
    """Faction that must fulfill a retreat for this outcome, if any."""

    if outcome == "attacker_retreat":
        u = state.board.units.get(attacker_id)
        return u.faction if u else None
    if outcome == "defender_retreat":
        u = state.board.units.get(defender_id)
        return u.faction if u else None
    return None


@dataclass(frozen=True, slots=True)
class CombatInteractionMessagesContext:
    """Inputs for ``UIHook.COMBAT_INTERACTION_MESSAGES``."""

    state: GameState
    viewer_faction: str | None
    extension_key: str | None
    current_segment: Mapping[str, Any] | None = None


def default_combat_interaction_messages(
    ctx: CombatInteractionMessagesContext,
    *,
    combat_instruction: Callable[[str, str | None], tuple[str, str]],
    advance_gate_banners: Callable[[str], tuple[str, str]],
) -> list[dict[str, Any]]:
    """
    Engine default combat/retreat/advance rows for ``interaction_messages``.

    Advance and retreat prompts follow ``current_segment.kind``; the title bucket
    ``combat_gate`` mirror is not read.
    """

    ek = str(ctx.extension_key or "").strip()
    if not ek:
        return []
    hx = title_bucket(ctx.state, ek)
    if not hx:
        return []

    segment = ctx.current_segment if isinstance(ctx.current_segment, Mapping) else None
    segment_kind = str(segment.get("kind", "")).strip() if segment else ""

    out: list[dict[str, Any]] = []
    viewer = str(ctx.viewer_faction).strip() if ctx.viewer_faction else ""

    last_combat = hx.get("last_combat")
    if isinstance(last_combat, dict):
        outcome = str(last_combat.get("outcome", ""))
        attacker_id = str(last_combat.get("attacker_id", ""))
        defender_id = str(last_combat.get("defender_id", ""))
        retreat_owner = retreat_owner_faction(
            ctx.state, outcome, attacker_id, defender_id
        )
        inst, msg = combat_instruction(outcome, retreat_owner)
        if inst in ("retreat_required", "wait") and segment_kind not in KIND_DOCK_ARC_RETREAT:
            inst, msg = "resolved", "Combat resolved."
        kind = (
            "retreat"
            if inst == "retreat_required"
            else "wait"
            if inst == "wait"
            else "info"
        )
        out.append(
            {
                "schema": 1,
                "kind": kind,
                "dedupe_key": "combat_prompt",
                "ttl_ms": None if kind in ("retreat", "wait") else 4_000,
                "css_class": (
                    "interaction-msg--retreat"
                    if kind == "retreat"
                    else "interaction-msg--wait"
                    if kind == "wait"
                    else "interaction-msg--info"
                ),
                "text": msg,
            }
        )

    if segment_kind in KIND_DOCK_ARC_ADVANCE:
        adv = hx.get("advance")
        adv_faction = (
            str(adv.get("faction", "")).strip() if isinstance(adv, dict) else ""
        )
        if adv_faction:
            t_adv, t_wait = advance_gate_banners(adv_faction)
            if adv_faction == viewer:
                out.append(
                    {
                        "schema": 1,
                        "kind": "advance",
                        "dedupe_key": "combat_advance",
                        "ttl_ms": None,
                        "css_class": "interaction-msg--advance",
                        "text": t_adv,
                    }
                )
            else:
                out.append(
                    {
                        "schema": 1,
                        "kind": "wait",
                        "dedupe_key": "combat_advance_wait",
                        "ttl_ms": None,
                        "css_class": "interaction-msg--wait",
                        "text": t_wait,
                    }
                )

    return out


__all__ = [
    "CombatInteractionMessagesContext",
    "default_combat_interaction_messages",
    "retreat_owner_faction",
]
