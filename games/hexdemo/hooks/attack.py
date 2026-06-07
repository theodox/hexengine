"""Thin ``AttackHook`` adapters — combat policy lives in ``combat_rules.py``."""

from __future__ import annotations

from typing import Any

from hexengine.hexes.types import Hex
from hexengine.hooks.attack import (
    AttackHook,
    AttackHooks,
    AttackPlanPreviewContext,
)
from hexengine.hooks.wiring import bind_title_hook

from .. import combat_rules, title_state
from ..arc_segment import phase_advance_blocked

# Re-export for tests that patch RNG on the rules module path.
random = combat_rules.random


@bind_title_hook(AttackHook.VALIDATE_ATTACK)
def validate_attack(ctx):
    return combat_rules.validate_attack(ctx)


@bind_title_hook(AttackHook.RESOLVE_ATTACK)
def resolve_attack(ctx):
    return combat_rules.resolve_attack(ctx)


@bind_title_hook(AttackHook.COMBAT_OUTCOME_AFTER_APPLIED)
def combat_outcome_after_applied(ctx):
    return combat_rules.combat_outcome_after_applied(ctx)


@bind_title_hook(AttackHook.AUTO_ADVANCE_PHASE_AFTER_ATTACK)
def auto_advance_phase_after_attack(state) -> bool:
    if phase_advance_blocked(state):
        return False
    phase = str(state.turn.current_phase)
    if phase not in ("Combat", "Attack"):
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
    for uid in title_state.attacks_this_phase(state):
        u = state.board.units.get(uid)
        if u is not None and u.active and u.faction == faction:
            attacked.add(uid)
    return active_ids <= attacked


@bind_title_hook(AttackHook.ATTACK_PLAN_PREVIEW)
def attack_plan_preview(ctx: AttackPlanPreviewContext) -> dict[str, Any]:
    from ..combat_planning import compute_attack_plan_preview

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

    pack_attack = AttackHooks(
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
        attack_hooks=pack_attack,
    )
