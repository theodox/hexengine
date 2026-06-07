"""
Shared authority attack commit helpers (imperative pipeline and combat arc effects).
"""

from __future__ import annotations

from typing import Any, Protocol

from ...hooks.attack import (
    AfterAttackAppliedContext,
    AttackContext,
    AttackResolution,
)
from ...hooks.combat_outcome import CombatOutcome
from ...hooks.core import ENGINE_DEFAULT
from ...hooks.title import TitleHooks
from ...snapshot import attack_resolution_snapshot_fields
from ...state.action_manager import ActionManager, StateAction
from ...state.actions import ApplyCombatEffects, Attack
from .authority_attack_wire import (
    normalize_attack_party_ids,
    optional_wire_hex_frozenset,
    sorted_unique_hexes_from_unit_ids,
)
from .combat_outcome_apply import (
    follow_up_state_actions_after_attack,
    split_resolve_result,
)


class AttackCommitHost(Protocol):
    hooks: TitleHooks
    action_manager: ActionManager


def build_attack_context_from_wire(
    state,
    player_faction: str,
    params: dict[str, Any],
) -> AttackContext:
    """Normalize wire parties and build ``AttackContext`` (raises on bad wire)."""

    attack_kind = str(params.get("attack_kind", ""))
    att = str(params.get("attacker_id", ""))
    deff = str(params.get("defender_id", ""))
    if not att or not deff:
        raise ValueError("Attack requires attacker_id and defender_id")
    au = state.board.units.get(att)
    du = state.board.units.get(deff)
    if au is None or du is None:
        raise ValueError("Unknown attacker or defender unit id")
    attacker_ids = normalize_attack_party_ids(
        params, anchor_id=att, plural_key="attacker_ids"
    )
    defender_ids = normalize_attack_party_ids(
        params, anchor_id=deff, plural_key="defender_ids"
    )
    for aid in attacker_ids:
        a = state.board.units.get(aid)
        if a is None or not a.active:
            raise ValueError("Unknown attacker or inactive unit")
        if a.faction != player_faction:
            raise ValueError("You do not control one of the attackers")
    for did in defender_ids:
        d = state.board.units.get(did)
        if d is None or not d.active:
            raise ValueError("Unknown defender or inactive unit")
        if au.faction == d.faction:
            raise ValueError("Cannot attack same faction")
    attacker_hexes = sorted_unique_hexes_from_unit_ids(state, attacker_ids)
    defender_hexes = sorted_unique_hexes_from_unit_ids(state, defender_ids)
    wire_att_hexes = optional_wire_hex_frozenset(params, "attacker_hexes")
    wire_def_hexes = optional_wire_hex_frozenset(params, "defender_hexes")
    if wire_att_hexes is not None and wire_att_hexes != frozenset(attacker_hexes):
        raise ValueError("attacker_hexes does not match attacker unit positions")
    if wire_def_hexes is not None and wire_def_hexes != frozenset(defender_hexes):
        raise ValueError("defender_hexes does not match defender unit positions")
    return AttackContext(
        state=state,
        attacker_ids=attacker_ids,
        defender_ids=defender_ids,
        attacker_hexes=attacker_hexes,
        defender_hexes=defender_hexes,
        player_faction=player_faction,
        attack_kind=attack_kind,
        params=params,
    )


def resolve_authority_attack(
    host: AttackCommitHost,
    ctx: AttackContext,
) -> tuple[AttackResolution, CombatOutcome | None]:
    """Run title validate + resolve; raise when unsupported or invalid."""

    hv = host.hooks.attack.validate(ctx)
    if hv is ENGINE_DEFAULT:
        raise ValueError("This game title does not support Attack actions")
    resolve_raw = host.hooks.attack.resolve(ctx)
    if resolve_raw is ENGINE_DEFAULT:
        raise ValueError("This game title does not resolve Attack actions")
    return split_resolve_result(resolve_raw)


def collect_authority_attack_actions(
    host: AttackCommitHost,
    *,
    attack_context: AttackContext,
    resolution: AttackResolution,
    extension_key: str,
    outcome_from_resolve: CombatOutcome | None = None,
) -> list[StateAction]:
    """State actions for ``Attack``, effects, and post-attack bucket handoff."""

    att = str(attack_context.params.get("attacker_id", ""))
    deff = str(attack_context.params.get("defender_id", ""))
    attack_kind = str(attack_context.params.get("attack_kind", ""))
    hr_att = resolution.attacker_ids
    hr_def = resolution.defender_ids
    n_rng, n_eff = attack_resolution_snapshot_fields(
        rng_entry=resolution.rng_entry,
        effects=resolution.effects,
    )
    actions: list[StateAction] = [
        Attack(
            attack_kind,
            att,
            deff,
            outcome=str(resolution.outcome or ""),
            attacker_ids=hr_att if hr_att is not None else attack_context.attacker_ids,
            defender_ids=hr_def if hr_def is not None else attack_context.defender_ids,
            retreat_distance=resolution.retreat_distance,
            retreat_unit_id=resolution.retreat_unit_id,
            rng_entry=n_rng,
        )
    ]
    if n_eff:
        actions.append(ApplyCombatEffects(n_eff))

    st_after = attack_context.state
    for action in actions:
        st_after = action.apply(st_after)

    follow_ctx = AfterAttackAppliedContext(
        state=st_after,
        attack_context=attack_context,
        resolution=resolution,
        extension_key=extension_key,
        player_faction=attack_context.player_faction,
    )
    actions.extend(
        follow_up_state_actions_after_attack(
            host.hooks,
            follow_ctx,
            outcome_from_resolve=outcome_from_resolve,
        )
    )
    return actions


def execute_authority_attack_commit(
    host: AttackCommitHost,
    *,
    attack_context: AttackContext,
    resolution: AttackResolution,
    extension_key: str,
    outcome_from_resolve: CombatOutcome | None = None,
) -> None:
    """Apply attack commit actions through the host action manager."""

    for action in collect_authority_attack_actions(
        host,
        attack_context=attack_context,
        resolution=resolution,
        extension_key=extension_key,
        outcome_from_resolve=outcome_from_resolve,
    ):
        host.action_manager.execute(action)


__all__ = [
    "AttackCommitHost",
    "build_attack_context_from_wire",
    "collect_authority_attack_actions",
    "execute_authority_attack_commit",
    "resolve_authority_attack",
]
