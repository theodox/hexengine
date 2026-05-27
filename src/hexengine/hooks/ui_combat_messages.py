"""Combat-related interaction message rows and phase-advance blocking policy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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


def default_blocks_routine_phase_advance(
    state: GameState, extension_key: str | None
) -> bool:
    """
    Engine catalog default: block routine phase advance during combat gates or
    positive ``retreat_obligations`` in the title bucket.
    """

    ek = str(extension_key or "").strip()
    if not ek:
        return False
    hx = title_bucket(state, ek)
    gate = str(hx.get("combat_gate", "")).strip()
    if gate in (
        "awaiting_retreat",
        "awaiting_retreat_or_disrupt",
        "awaiting_advance",
    ):
        return True
    ro = hx.get("retreat_obligations")
    if isinstance(ro, dict):
        for raw in ro.values():
            try:
                if int(raw) > 0:
                    return True
            except (TypeError, ValueError):
                continue
    return False


@dataclass(frozen=True, slots=True)
class CombatInteractionMessagesContext:
    """Inputs for ``UIHook.COMBAT_INTERACTION_MESSAGES``."""

    state: GameState
    viewer_faction: str | None
    extension_key: str | None


def default_combat_interaction_messages(
    ctx: CombatInteractionMessagesContext,
    *,
    combat_instruction: Callable[[str, str | None], tuple[str, str]],
    advance_gate_banners: Callable[[str], tuple[str, str]],
) -> list[dict[str, Any]]:
    """
    Engine default combat/retreat/advance rows for ``interaction_messages``.

    ``combat_instruction`` and ``advance_gate_banners`` usually delegate to
    ``UIHooks`` (title copy) or engine defaults.
    """

    ek = str(ctx.extension_key or "").strip()
    if not ek:
        return []
    hx = title_bucket(ctx.state, ek)
    if not hx:
        return []

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
        gate = str(hx.get("combat_gate", "")).strip()
        if inst in ("retreat_required", "wait") and gate not in (
            "awaiting_retreat",
            "awaiting_retreat_or_disrupt",
        ):
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

    gate = str(hx.get("combat_gate", "")).strip()
    if gate == "awaiting_advance":
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
    "default_blocks_routine_phase_advance",
    "default_combat_interaction_messages",
    "retreat_owner_faction",
]
