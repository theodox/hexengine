"""
Authority-side `Attack` request pipeline (server → hooks → state → broadcast).

This module names the **ordered steps** the engine runs for a single client
`Attack` action. Related **cleanup** interactions (mandatory retreat moves, disrupt-instead,
combat advance) are implemented in `hexengine.server.arcs.authority_combat_cleanup`. Stepwise
movement is `hexengine.server.arcs.authority_movement`; together with this file they form
three server-side **arcs** (vocabulary in `hexengine.state.movement_arc`).

Titles customize behavior via `TitleHooks.attack` (validate / resolve / auto-advance);
this file is the stable **orchestration** surface for authors reading the engine.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any, Protocol

from ...hexes.types import Hex
from ...hooks.attack import AfterAttackAppliedContext, AttackContext, AttackResolution
from ...hooks.core import ENGINE_DEFAULT
from ...state.action_manager import StateAction
from ...hooks.title import TitleHooks
from ...snapshot import attack_resolution_snapshot_fields
from ...state import GameState
from ...state.action_manager import ActionManager
from ...state.actions import ApplyCombatEffects, Attack
from .authority_arc_runtime import begin_combat_arc


def dedupe_wire_id_list(raw: Any) -> list[str]:
    """Stable de-dupe of string ids from a wire list field."""
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for x in raw:
        if isinstance(x, str) and (s := x.strip()) and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def normalize_attack_party_ids(
    params: dict[str, Any], *, anchor_id: str, plural_key: str
) -> tuple[str, ...]:
    """Build ordered (anchor first) party ids from wire anchor + optional plural list."""
    anchor = str(anchor_id or "").strip()
    if not anchor:
        return ()
    extras = dedupe_wire_id_list(params.get(plural_key))
    if not extras:
        return (anchor,)
    if anchor not in extras:
        return (anchor, *extras)
    rest = [x for x in extras if x != anchor]
    return (anchor, *rest)


def sorted_unique_hexes_from_unit_ids(
    state: GameState, unit_ids: tuple[str, ...]
) -> tuple[Hex, ...]:
    """Distinct hex positions of active units with the given ids (sorted for stability)."""
    seen: set[tuple[int, int, int]] = set()
    hs: list[Hex] = []
    for uid in unit_ids:
        u = state.board.units.get(uid)
        if u is None or not u.active:
            continue
        t = (int(u.position.i), int(u.position.j), int(u.position.k))
        if t in seen:
            continue
        seen.add(t)
        hs.append(u.position)
    return tuple(sorted(hs, key=lambda h: (int(h.i), int(h.j), int(h.k))))


def optional_wire_hex_frozenset(
    params: dict[str, Any], key: str
) -> frozenset[Hex] | None:
    """If `params[key]` is a list of `{i,j,k}`, return those hexes; else None."""
    raw = params.get(key)
    if not isinstance(raw, list) or not raw:
        return None
    out: list[Hex] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        try:
            out.append(Hex(int(row["i"]), int(row["j"]), int(row["k"])))
        except (KeyError, TypeError, ValueError):
            continue
    return frozenset(out) if out else None


class AuthorityAttackPipelineStep(StrEnum):
    """Named **segments** of one authority `Attack` RPC within the combat **arc**."""

    NORMALIZE_WIRE_AND_PARTIES = "normalize_wire_and_parties"
    HOOK_VALIDATE = "hook_validate"
    HOOK_RESOLVE = "hook_resolve"
    REQUIRE_TITLE_EXTENSION_KEY = "require_title_extension_key"
    COMMIT_ATTACK_AND_EFFECTS = "commit_attack_and_effects"
    AFTER_ATTACK_APPLIED = "after_attack_applied"
    BROADCAST_COMBAT_EVENTS = "broadcast_combat_events"
    MAYBE_AUTO_ADVANCE_PHASE = "maybe_auto_advance_phase"


ATTACK_BLOCKED_BY_ACTIVE_SEGMENT_MSG = (
    "Resolve combat obligations before issuing another attack"
)


AUTHORITY_ATTACK_PIPELINE: tuple[AuthorityAttackPipelineStep, ...] = (
    AuthorityAttackPipelineStep.NORMALIZE_WIRE_AND_PARTIES,
    AuthorityAttackPipelineStep.HOOK_VALIDATE,
    AuthorityAttackPipelineStep.HOOK_RESOLVE,
    AuthorityAttackPipelineStep.REQUIRE_TITLE_EXTENSION_KEY,
    AuthorityAttackPipelineStep.COMMIT_ATTACK_AND_EFFECTS,
    AuthorityAttackPipelineStep.AFTER_ATTACK_APPLIED,
    AuthorityAttackPipelineStep.BROADCAST_COMBAT_EVENTS,
    AuthorityAttackPipelineStep.MAYBE_AUTO_ADVANCE_PHASE,
)


class AuthorityAttackHost(Protocol):
    """Minimal `GameServer` surface used by `execute_authority_attack_request`."""

    hooks: TitleHooks
    action_manager: ActionManager
    logger: logging.Logger

    async def _send_error(self, player_id: str, message: str) -> None: ...

    def _title_extension_key(self) -> str | None: ...

    async def _broadcast_combat_events(self, state: GameState) -> None: ...

    def lookup_arc_spec(self, arc_id: str) -> object: ...

    def _get_next_phase(self) -> dict[str, Any]: ...

    def _after_next_phase_applied(self) -> None: ...

    def _maybe_auto_advance_phase(
        self,
        raw: bool | object,
        *,
        catalog_path: str | None,
        log_reason: str,
    ) -> bool: ...


async def execute_authority_attack_request(
    host: AuthorityAttackHost,
    *,
    player_id: str,
    player_faction: str,
    current_state: GameState,
    params: dict[str, Any],
) -> bool:
    """
    Run the authority pipeline for one `Attack` client request.

    Returns:
        True if the attack was committed and the caller should send success + state
        broadcast. False if an error was already sent to the player.
    """
    # --- NORMALIZE_WIRE_AND_PARTIES + HOOK_VALIDATE + HOOK_RESOLVE ---
    try:
        attack_kind = str(params.get("attack_kind", ""))
        att = str(params.get("attacker_id", ""))
        deff = str(params.get("defender_id", ""))
        if not att or not deff:
            raise ValueError("Attack requires attacker_id and defender_id")
        au = current_state.board.units.get(att)
        du = current_state.board.units.get(deff)
        if au is None or du is None:
            raise ValueError("Unknown attacker or defender unit id")
        attacker_ids = normalize_attack_party_ids(
            params, anchor_id=att, plural_key="attacker_ids"
        )
        defender_ids = normalize_attack_party_ids(
            params, anchor_id=deff, plural_key="defender_ids"
        )
        for aid in attacker_ids:
            a = current_state.board.units.get(aid)
            if a is None or not a.active:
                raise ValueError("Unknown attacker or inactive unit")
            if a.faction != player_faction:
                raise ValueError("You do not control one of the attackers")
        for did in defender_ids:
            d = current_state.board.units.get(did)
            if d is None or not d.active:
                raise ValueError("Unknown defender or inactive unit")
            if au.faction == d.faction:
                raise ValueError("Cannot attack same faction")
        attacker_hexes = sorted_unique_hexes_from_unit_ids(current_state, attacker_ids)
        defender_hexes = sorted_unique_hexes_from_unit_ids(current_state, defender_ids)
        wire_att_hexes = optional_wire_hex_frozenset(params, "attacker_hexes")
        wire_def_hexes = optional_wire_hex_frozenset(params, "defender_hexes")
        if wire_att_hexes is not None and wire_att_hexes != frozenset(attacker_hexes):
            raise ValueError("attacker_hexes does not match attacker unit positions")
        if wire_def_hexes is not None and wire_def_hexes != frozenset(defender_hexes):
            raise ValueError("defender_hexes does not match defender unit positions")
        ctx = AttackContext(
            state=current_state,
            attacker_ids=attacker_ids,
            defender_ids=defender_ids,
            attacker_hexes=attacker_hexes,
            defender_hexes=defender_hexes,
            player_faction=player_faction,
            attack_kind=attack_kind,
            params=params,
        )
        if host._title_extension_key():
            from ...arcs.segment_wire import segment_denies_action_for_faction

            if segment_denies_action_for_faction(
                host, current_state, player_faction, "Attack"
            ):
                raise ValueError(ATTACK_BLOCKED_BY_ACTIVE_SEGMENT_MSG)
        hv = host.hooks.attack.validate(ctx)
        if hv is ENGINE_DEFAULT:
            raise ValueError("This game title does not support Attack actions")
        hr = host.hooks.attack.resolve(ctx)
        if hr is ENGINE_DEFAULT:
            raise ValueError("This game title does not resolve Attack actions")
    except Exception as e:
        await host._send_error(player_id, str(e))
        return False

    # --- REQUIRE_TITLE_EXTENSION_KEY ---
    ek = host._title_extension_key()
    if not ek:
        await host._send_error(
            player_id,
            "This game title does not define a state extension key for combat",
        )
        return False

    # --- COMMIT_ATTACK_AND_EFFECTS ---
    try:
        hr_att = getattr(hr, "attacker_ids", None)
        hr_def = getattr(hr, "defender_ids", None)
        n_rng, n_eff = attack_resolution_snapshot_fields(
            rng_entry=getattr(hr, "rng_entry", None),
            effects=getattr(hr, "effects", None),
        )
        atk = Attack(
            attack_kind,
            att,
            deff,
            outcome=str(getattr(hr, "outcome", "")),
            attacker_ids=hr_att if hr_att is not None else ctx.attacker_ids,
            defender_ids=hr_def if hr_def is not None else ctx.defender_ids,
            retreat_distance=getattr(hr, "retreat_distance", None),
            retreat_unit_id=getattr(hr, "retreat_unit_id", None),
            rng_entry=n_rng,
        )
        host.action_manager.execute(atk)
        if n_eff:
            host.action_manager.execute(ApplyCombatEffects(n_eff))
    except Exception as e:
        await host._send_error(player_id, f"Action failed: {e}")
        return False

    # --- AFTER_ATTACK_APPLIED ---
    st_after = host.action_manager.current_state
    if not isinstance(hr, AttackResolution):
        raise TypeError("resolve_attack must return AttackResolution")
    follow_ctx = AfterAttackAppliedContext(
        state=st_after,
        attack_context=ctx,
        resolution=hr,
        extension_key=ek,
        player_faction=player_faction,
    )
    follow_raw = host.hooks.attack.follow_up_after_attack(follow_ctx)
    if follow_raw is not ENGINE_DEFAULT:
        if not isinstance(follow_raw, list):
            raise TypeError(
                "hooks.attack.after_attack_applied must return list[StateAction] or "
                "hooks.ENGINE_DEFAULT"
            )
        try:
            for action in follow_raw:
                if not isinstance(action, StateAction):
                    raise TypeError(
                        "hooks.attack.after_attack_applied entries must be StateAction"
                    )
                host.action_manager.execute(action)
        except Exception as e:
            await host._send_error(player_id, f"Action failed: {e}")
            return False
        st_after = host.action_manager.current_state

    # --- BEGIN COMBAT ARC ---
    # If the title declares a combat arc, start it now: its entry segment classifies the
    # combat state the follow-up just set and auto-advances to the matching gate (or
    # finishes when there is no cleanup). No-op for titles without a declared arc.
    begin_combat_arc(host)
    st_after = host.action_manager.current_state

    # --- BROADCAST_COMBAT_EVENTS ---
    await host._broadcast_combat_events(st_after)

    # --- MAYBE_AUTO_ADVANCE_PHASE ---
    adv = host.hooks.attack.auto_advance(st_after)
    host._maybe_auto_advance_phase(
        adv,
        catalog_path=None,
        log_reason=(
            f"after attack ({st_after.turn.current_faction} "
            f"{st_after.turn.current_phase})"
        ),
    )

    return True


__all__ = [
    "ATTACK_BLOCKED_BY_ACTIVE_SEGMENT_MSG",
    "AUTHORITY_ATTACK_PIPELINE",
    "AuthorityAttackHost",
    "AuthorityAttackPipelineStep",
    "dedupe_wire_id_list",
    "execute_authority_attack_request",
    "normalize_attack_party_ids",
    "optional_wire_hex_frozenset",
    "sorted_unique_hexes_from_unit_ids",
]
