"""Thin ``InteractionHook`` adapters — policy lives in ``combat/rules.py``."""

from __future__ import annotations

from hexengine.hexes.types import Hex
from hexengine.hooks.interaction import (
    AttackPlanPreviewContext,
    InteractionHook,
    InteractionHooks,
)
from hexengine.hooks.wiring import bind_title_hook

from ..arcs.segment import attack_allowed_for_faction, phase_advance_blocked
from ..combat import rules as combat_rules
from ..combat.planning import compute_attack_plan_preview
from ..state import session_state

random = combat_rules.random


@bind_title_hook(InteractionHook.VALIDATE_ATTACK)
def validate_attack(ctx):
    return combat_rules.validate_attack(ctx)


@bind_title_hook(InteractionHook.RESOLVE_ATTACK)
def resolve_attack(ctx):
    return combat_rules.resolve_attack(ctx)


@bind_title_hook(InteractionHook.COMBAT_OUTCOME_AFTER_APPLIED)
def combat_outcome_after_applied(ctx):
    return combat_rules.combat_outcome_after_applied(ctx)


@bind_title_hook(InteractionHook.AUTO_ADVANCE_PHASE_AFTER_ATTACK)
def auto_advance_phase_after_attack(state) -> bool:
    if phase_advance_blocked(state):
        return False
    if not attack_allowed_for_faction(state, state.turn.current_faction):
        return False
    faction = state.turn.current_faction
    active_ids = {
        u.unit_id
        for u in state.board.units.values()
        if u.active and u.faction == faction
    }
    if not active_ids:
        return True
    attacked: set[str] = set()
    for uid in session_state.attacks_this_phase(state):
        u = state.board.units.get(uid)
        if u is not None and u.active and u.faction == faction:
            attacked.add(uid)
    return active_ids <= attacked


@bind_title_hook(InteractionHook.ATTACK_PLAN_PREVIEW)
def attack_plan_preview(ctx: AttackPlanPreviewContext):
    st = ctx.state
    seen: set[tuple[int, int, int]] = set()
    board_hexes: list[Hex] = []
    for u in st.board.units.values():
        if not u.active:
            continue
        t = (int(u.position.i), int(u.position.j), int(u.position.k))
        if t not in seen:
            seen.add(t)
            board_hexes.append(u.position)
    for loc in st.board.locations.values():
        h = loc.position
        t = (int(h.i), int(h.j), int(h.k))
        if t not in seen:
            seen.add(t)
            board_hexes.append(h)

    pack_interaction = InteractionHooks(
        validate_attack=validate_attack,
        resolve_attack=resolve_attack,
        auto_advance_phase_after_attack=auto_advance_phase_after_attack,
        attack_plan_preview=attack_plan_preview,
    )
    return compute_attack_plan_preview(
        st,
        player_faction=ctx.player_faction,
        draft=ctx.draft,
        shell_ui=ctx.shell_ui,
        board_hexes=board_hexes,
        interaction_hooks=pack_interaction,
    )


__all__ = [
    "attack_plan_preview",
    "auto_advance_phase_after_attack",
    "combat_outcome_after_applied",
    "random",
    "resolve_attack",
    "validate_attack",
]
