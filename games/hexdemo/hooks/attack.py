from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, auto

from hexengine.hexes.los import has_line_of_sight
from hexengine.hexes.math import distance
from hexengine.hexes.types import Hex
from typing import Any

from hexengine.hooks.attack import (
    AfterAttackAppliedContext,
    AttackContext,
    AttackHook,
    AttackHooks,
    AttackPlanPreviewContext,
    AttackResolution,
    CombatAdvanceMoveContext,
    CombatCleanupContext,
    RetreatObligationClearedContext,
)
from hexengine.hooks.wiring import bind_title_hook
from hexengine.state import UnitState
from hexengine.state.map_feature_queries import edges_block_los_predicate

from .. import arc_segment
from .. import combat
from .. import combat_transitions
from .. import title_state
from ..constants import PACK_STATE_EXTENSION_KEY

# When the board has no explicit or unset-default terrain for a hex, CRT math still
# needs a stable type (matches legacy tests and minimal `BoardState` fixtures).
_DEFAULT_TERRAIN_TYPE = "plain"


def _terrain_type_for_hex(board, h: Hex) -> str:
    loc = board.effective_location(h)
    if loc is None:
        return _DEFAULT_TERRAIN_TYPE
    return str(loc.terrain_type)


def _terrain_blocks_los(ctx: AttackContext):
    board = ctx.state.board

    def blocks(h):
        loc = board.effective_location(h)
        if loc is None:
            return False
        return bool(getattr(loc, "block_los", False))

    return blocks


def _los_edges_block(ctx: AttackContext):
    return edges_block_los_predicate(ctx.state.board)


def _expected_enemy_defender_ids(ctx: AttackContext) -> tuple[str, ...]:
    """Every active enemy unit on any `ctx.defender_hexes` cell."""
    attacker = ctx.state.board.units.get(ctx.attacker_unit_id)
    if attacker is None or not attacker.active:
        return ()
    out: list[str] = []
    seen: set[str] = set()
    for h in ctx.defender_hexes:
        for u in ctx.state.board.active_units_at_hex(h):
            if u.faction != attacker.faction and u.unit_id not in seen:
                seen.add(u.unit_id)
                out.append(str(u.unit_id))
    return tuple(sorted(out))


def _infantry_adjacent_to_any_defender_hex(a, defender_hexes: tuple[Hex, ...]) -> bool:
    return any(distance(a.position, h) == 1 for h in defender_hexes)


def _artillery_can_hit_any_defender_hex(
    a,
    defender_hexes: tuple[Hex, ...],
    blocks,
    *,
    edges_block,
) -> bool:
    raw_range = a.attributes.get("range")
    try:
        atk_range = int(raw_range) if raw_range is not None else 0
    except Exception:
        atk_range = 0
    if atk_range <= 1:
        return False
    for h in defender_hexes:
        dist = distance(a.position, h)
        if (
            dist > 1
            and dist <= atk_range
            and has_line_of_sight(
                a.position,
                h,
                blocks=blocks,
                edges_block=edges_block,
            )
        ):
            return True
    return False


@bind_title_hook(AttackHook.VALIDATE_ATTACK)
def validate_attack(ctx: AttackContext) -> None:
    if ctx.attack_kind not in ("combined",):
        raise ValueError(f"Unknown attack_kind for hexdemo: {ctx.attack_kind!r}")
    phase = str(ctx.state.turn.current_phase)
    if phase not in ("Combat", "Attack"):
        raise ValueError("Attacks are only allowed during the combat phase")
    if ctx.player_faction != ctx.state.turn.current_faction:
        raise ValueError("Not your turn")
    if combat.any_retreat_obligation_pending(ctx.state):
        raise ValueError("Resolve retreat before issuing another attack")
    if arc_segment.segment_denies_action(ctx.state, ctx.player_faction, "Attack"):
        raise ValueError("Resolve combat obligations before issuing another attack")

    att_primary = ctx.state.board.units.get(ctx.attacker_unit_id)
    if att_primary is None or not att_primary.active:
        raise ValueError("Invalid attacker")
    if att_primary.faction != ctx.player_faction:
        raise ValueError("You do not control the attacker")

    for did in ctx.defender_ids:
        d = ctx.state.board.units.get(did)
        if d is None or not d.active:
            raise ValueError("Invalid defender")
        if d.faction == att_primary.faction:
            raise ValueError("Cannot attack same faction")

    expected = set(_expected_enemy_defender_ids(ctx))
    if not expected:
        raise ValueError("No enemy units on defender hex(es)")
    if set(ctx.defender_ids) != expected:
        raise ValueError(
            "Defender list must include every enemy on the defender hex(es)"
        )

    defender_hexes = ctx.defender_hexes
    blocks = _terrain_blocks_los(ctx)
    edges_block = _los_edges_block(ctx)
    for aid in ctx.attacker_ids:
        a = ctx.state.board.units.get(aid)
        if a is None or not a.active:
            raise ValueError("Invalid attacker")
        if a.faction != ctx.player_faction:
            raise ValueError("You do not control the attacker")
        ut = str(a.unit_type).lower()
        if ut in ("infantry", "inf"):
            if not _infantry_adjacent_to_any_defender_hex(a, defender_hexes):
                raise ValueError("Infantry attacker is not adjacent to the target")
        elif ut in ("artillery", "art"):
            if not _artillery_can_hit_any_defender_hex(
                a, defender_hexes, blocks, edges_block=edges_block
            ):
                raise ValueError("No line of sight to target")
        else:
            raise ValueError(f"Unit type {ut!r} cannot participate in combined attacks")

    prev = title_state.bucket(ctx.state).get("attacks_this_phase")
    if isinstance(prev, list):
        for aid in ctx.attacker_ids:
            if aid in prev:
                raise ValueError("That unit has already attacked this combat phase")

    params = ctx.params if isinstance(ctx.params, dict) else {}
    pa = params.get("primary_attacker_id")
    if isinstance(pa, str) and pa.strip():
        s = pa.strip()
        if s not in ctx.attacker_ids:
            raise ValueError("primary_attacker_id must be one of the attackers")
    pd = params.get("primary_defender_id")
    if isinstance(pd, str) and pd.strip():
        s = pd.strip()
        if s not in ctx.defender_ids:
            raise ValueError("primary_defender_id must be one of the defenders")


# (attacker terrain, defender terrain) -> multiplier; extend when balancing hexdemo combat.
_TERRAIN_COMBAT_MULT: dict[tuple[str, str], float] = {
    ("plain", "plain"): 1.0,
    ("plain", "light woods"): 1.0,
    ("plain", "deep woods"): 0.5,
    ("plain", "hills"): 0.5,
    ("hills", "hills"): 1.0,
    ("hills", "light woods"): 0.5,
    ("hills", "deep woods"): 0.5,
    ("deep woods", "light woods"): 0.25,
    ("deep woods", "deep woods"): 0.25,
    ("deep woods", "plain"): 0.5,
    ("deep woods", "hills"): 0.5,
    ("light woods", "plain"): 1.0,
    ("light woods", "light woods"): 1.0,
    ("light woods", "deep woods"): 0.5,
    ("light woods", "hills"): 0.5,
}


def get_combat_factor(
    unit: UnitState, attacker_hex_type: str, defender_hex_type: str
) -> float:
    raw_value = unit.attributes.get("combat", 0)
    key = (attacker_hex_type, defender_hex_type)
    mult = _TERRAIN_COMBAT_MULT.get(key, 1.0)
    return raw_value * mult


class CombatOutcome(Enum):
    NO_EFFECT = auto()
    RETREAT = auto()
    DISRUPT = auto()
    EXCHANGE = auto()
    ROUT = auto()
    LOSS = auto()


@dataclass
class CombatResult:
    side: str
    passed: CombatOutcome
    failed: CombatOutcome


AX = CombatResult(side="a", passed=CombatOutcome.LOSS, failed=CombatOutcome.DISRUPT)
AR = CombatResult(side="a", passed=CombatOutcome.RETREAT, failed=None)
AC_NE = CombatResult(
    side="a", passed=CombatOutcome.NO_EFFECT, failed=CombatOutcome.RETREAT
)
AC_EX = CombatResult(
    side="a", passed=CombatOutcome.EXCHANGE, failed=CombatOutcome.RETREAT
)
AM_R = CombatResult(side="a", passed=CombatOutcome.RETREAT, failed=CombatOutcome.ROUT)
DX = CombatResult(side="d", passed=CombatOutcome.LOSS, failed=CombatOutcome.DISRUPT)
DR = CombatResult(side="d", passed=CombatOutcome.RETREAT, failed=None)
DC_NE = CombatResult(
    side="d", passed=CombatOutcome.NO_EFFECT, failed=CombatOutcome.RETREAT
)
DC_DR = CombatResult(
    side="d", passed=CombatOutcome.RETREAT, failed=CombatOutcome.DISRUPT
)
DC_DX = CombatResult(side="d", passed=CombatOutcome.LOSS, failed=CombatOutcome.ROUT)
DC_EX = CombatResult(
    side="d", passed=CombatOutcome.EXCHANGE, failed=CombatOutcome.RETREAT
)
DM_R = CombatResult(side="d", passed=CombatOutcome.RETREAT, failed=CombatOutcome.ROUT)
DM_X = CombatResult(side="d", passed=CombatOutcome.LOSS, failed=CombatOutcome.ROUT)


def check_morale(unit: UnitState) -> bool:
    """
    Morale check: roll 1..6 and pass when roll <= morale (0..6).

    Using 1..6 inclusive prevents morale 6 from being an automatic pass under
    an off-by-one range bug (1..5).
    """
    try:
        morale = int(unit.attributes.get("morale", 0))
    except (TypeError, ValueError):
        morale = 0
    morale = max(0, min(6, morale))
    roll = random.randrange(1, 7)
    return roll <= morale


def _resolve_primary_attacker_id(ctx: AttackContext) -> str:
    params = ctx.params if isinstance(ctx.params, dict) else {}
    raw = params.get("primary_attacker_id")
    if isinstance(raw, str):
        s = raw.strip()
        if s and s in ctx.attacker_ids:
            return s
    return ctx.attacker_unit_id


def _resolve_primary_defender_id(ctx: AttackContext) -> str:
    params = ctx.params if isinstance(ctx.params, dict) else {}
    raw = params.get("primary_defender_id")
    if isinstance(raw, str):
        s = raw.strip()
        if s and s in ctx.defender_ids:
            return s
    return ctx.defender_unit_id


def _stack_unit_ids(state, anchor_unit_id: str) -> tuple[str, ...]:
    u = state.board.units.get(anchor_unit_id)
    if u is None or not u.active:
        return ()
    out: list[str] = []
    for x in state.board.active_units_at_hex(u.position):
        if x.active and x.faction == u.faction:
            out.append(str(x.unit_id))
    return tuple(sorted(out))


def _attack_includes_adjacent_infantry(ctx: AttackContext) -> bool:
    """True if any participating attacker is infantry (must be adjacent per `validate_attack`)."""
    for aid in ctx.attacker_ids:
        a = ctx.state.board.units.get(aid)
        if a is None or not a.active:
            continue
        ut = str(a.unit_type).strip().lower()
        if ut in ("infantry", "inf"):
            return True
    return False


@bind_title_hook(AttackHook.RESOLVE_ATTACK)
def resolve_attack(ctx: AttackContext) -> AttackResolution:
    if ctx.attack_kind not in ("combined",):
        raise ValueError(f"Unknown attack_kind for hexdemo: {ctx.attack_kind!r}")

    d_hex_type = _terrain_type_for_hex(ctx.state.board, ctx.defender_hex)

    attack_factors = 0

    for aid in ctx.attacker_ids:
        a = ctx.state.board.units.get(aid)
        if a is None or not a.active:
            raise ValueError("Invalid attacker")
        a_hex_type = _terrain_type_for_hex(ctx.state.board, a.position)
        attack_factors += get_combat_factor(a, a_hex_type, d_hex_type)

    defense_factors = 0

    for did in ctx.defender_ids:
        d = ctx.state.board.units.get(did)
        if d is None or not d.active:
            raise ValueError("Invalid defender")
        defense_factors += d.attributes.get("combat", 0)

    if d_hex_type == "strongpoint":
        defense_factors += 2

    primary_aid = _resolve_primary_attacker_id(ctx)
    primary_did = _resolve_primary_defender_id(ctx)
    primary_attacker = ctx.state.board.units.get(primary_aid)
    primary_defender = ctx.state.board.units.get(primary_did)
    if primary_attacker is None or not primary_attacker.active:
        raise ValueError("Invalid primary attacker")
    if primary_defender is None or not primary_defender.active:
        raise ValueError("Invalid primary defender")

    column = round(attack_factors - defense_factors)
    column = min(column, 10)
    column = max(column, -5)

    values = None

    match column:
        case -5:
            values = (AX, AX, AX, AR, AR, AR)
        case -4 | -3:
            values = (AX, AX, AR, AR, AC_NE, DC_NE)
        case -2 | -1:
            values = (AX, AR, AR, AC_EX, DC_NE, DC_DR)
        case 0 | 1:
            values = (AR, AR, AC_EX, DC_EX, DR, DR)
        case 2 | 3:
            values = (AC_NE, DC_EX, DC_EX, DR, DR, DM_R)
        case 4 | 5:
            values = (DC_EX, DC_EX, DR, DR, DM_R, DM_R)
        case 6 | 7:
            values = (DR, DR, DX, DM_R, DM_R, DM_X)
        case 8 | 9:
            values = (DR, DX, DM_R, DM_R, DM_X, DM_X)
        case 10:
            values = (DX, DM_R, DM_R, DM_X, DM_X, DM_X, DM_X)
        case _:
            raise ValueError(f"Invalid column: {column}")

    roll = random.randrange(0, len(values))
    crt = values[roll]

    if crt.side == "a":
        mc = check_morale(primary_attacker)
    else:
        mc = check_morale(primary_defender)

    if mc:
        result = crt.passed
    else:
        result = crt.failed

    if result is None:
        result = CombatOutcome.NO_EFFECT

    # Ranged-only attacks (no adjacent infantry in the attacker party): artillery may
    # bombard from range but never suffers attacker retreat or rout. Defender retreats
    # (e.g. artillery shelled by infantry) are unchanged.
    attacker_retreat_suppressed = False
    if (
        not _attack_includes_adjacent_infantry(ctx)
        and crt.side == "a"
        and result in (CombatOutcome.RETREAT, CombatOutcome.ROUT)
    ):
        attacker_retreat_suppressed = True
        if result == CombatOutcome.ROUT:
            result = CombatOutcome.DISRUPT
        else:
            result = CombatOutcome.NO_EFFECT

    st = ctx.state
    effects: dict = {"schema": 1}
    step_losses: list[dict[str, object]] = []
    disrupt_ids: list[str] = []
    retreat_allow_disrupt = False

    engine_outcome = "none"
    retreat_distance: int | None = None
    retreat_unit_id: str | None = None

    if result == CombatOutcome.NO_EFFECT:
        pass
    elif result == CombatOutcome.RETREAT:
        retreat_allow_disrupt = True
        retreat_distance = 1
        if crt.side == "a":
            engine_outcome = "attacker_retreat"
            retreat_unit_id = primary_aid
        else:
            engine_outcome = "defender_retreat"
            retreat_unit_id = primary_did
    elif result == CombatOutcome.ROUT:
        retreat_distance = 3
        if crt.side == "a":
            engine_outcome = "attacker_retreat"
            retreat_unit_id = primary_aid
            disrupt_ids.extend(_stack_unit_ids(st, primary_aid))
        else:
            engine_outcome = "defender_retreat"
            retreat_unit_id = primary_did
            disrupt_ids.extend(_stack_unit_ids(st, primary_did))
    elif result == CombatOutcome.LOSS:
        anchor = primary_aid if crt.side == "a" else primary_did
        for uid in _stack_unit_ids(st, anchor):
            step_losses.append({"unit_id": uid, "count": 1})
    elif result == CombatOutcome.DISRUPT:
        anchor = primary_aid if crt.side == "a" else primary_did
        disrupt_ids.extend(_stack_unit_ids(st, anchor))
    elif result == CombatOutcome.EXCHANGE:
        for uid in _stack_unit_ids(st, primary_aid):
            step_losses.append({"unit_id": uid, "count": 1})
        for uid in _stack_unit_ids(st, primary_did):
            step_losses.append({"unit_id": uid, "count": 1})
    else:
        raise ValueError(f"Unhandled combat outcome {result!r}")

    if step_losses:
        effects["step_losses"] = step_losses
    if disrupt_ids:
        effects["disrupt"] = list(dict.fromkeys(disrupt_ids))
    if retreat_allow_disrupt:
        effects["retreat"] = {"allow_disrupt_instead": True}

    effects["last_combat_patch"] = {
        "primary_attacker_id": primary_aid,
        "primary_defender_id": primary_did,
        "hexdemo_combat_result": result.name,
        "hexdemo_table_side": crt.side,
        "hexdemo_column": column,
        "hexdemo_roll": roll,
        "hexdemo_morale_passed": mc,
        "hexdemo_attacker_retreat_suppressed": attacker_retreat_suppressed,
    }

    rng_entry = {
        "op": "combined_attack",
        "schema": 1,
        "column": column,
        "roll": roll,
        "hexdemo_table_side": crt.side,
        "hexdemo_morale_passed": mc,
        "hexdemo_combat_result": result.name,
        "hexdemo_attacker_retreat_suppressed": attacker_retreat_suppressed,
        "attacker_id": ctx.attacker_unit_id,
        "attacker_ids": list(ctx.attacker_ids),
        "defender_id": ctx.defender_unit_id,
        "defender_ids": list(ctx.defender_ids),
        "primary_attacker_id": primary_aid,
        "primary_defender_id": primary_did,
        "retreat_distance": retreat_distance,
        "engine_outcome": engine_outcome,
        "attacker_hexes": [
            {"i": int(h.i), "j": int(h.j), "k": int(h.k)} for h in ctx.attacker_hexes
        ],
        "defender_hexes": [
            {"i": int(h.i), "j": int(h.j), "k": int(h.k)} for h in ctx.defender_hexes
        ],
    }
    return AttackResolution(
        outcome=engine_outcome,
        attacker_ids=None,
        defender_ids=None,
        retreat_distance=retreat_distance,
        retreat_unit_id=retreat_unit_id,
        rng_entry=rng_entry,
        effects=effects,
    )


@bind_title_hook(AttackHook.AFTER_ATTACK_APPLIED)
def after_attack_applied(ctx: AfterAttackAppliedContext) -> list:
    return combat_transitions.follow_up_after_attack(ctx)


@bind_title_hook(AttackHook.ON_RETREAT_OBLIGATION_CLEARED)
def on_retreat_obligation_cleared(
    ctx: RetreatObligationClearedContext,
) -> list:
    return combat_transitions.on_retreat_obligation_cleared(ctx)


@bind_title_hook(AttackHook.COMBAT_DISRUPT_INSTEAD_OF_RETREAT)
def combat_disrupt_instead_of_retreat(ctx: CombatCleanupContext) -> list:
    from .. import combat_actions

    return combat_actions.disrupt_instead_of_retreat(
        ctx.state, ctx.extension_key, ctx.player_faction
    )


@bind_title_hook(AttackHook.COMBAT_RESOLVE_ADVANCE)
def combat_resolve_advance(ctx: CombatCleanupContext) -> list:
    from .. import combat_actions

    return combat_actions.resolve_combat_advance(
        ctx.state, ctx.extension_key, ctx.player_faction
    )


@bind_title_hook(AttackHook.IS_COMBAT_ADVANCE_MOVE)
def is_combat_advance_move(ctx: CombatAdvanceMoveContext) -> bool:
    from .. import combat_actions

    return combat_actions.is_combat_advance_move(
        ctx.state, ctx.params, ctx.player_faction, ctx.extension_key
    )


@bind_title_hook(AttackHook.AUTO_ADVANCE_PHASE_AFTER_ATTACK)
def auto_advance_phase_after_attack(state) -> bool:
    """
    Advance the schedule when every active unit of the current faction has attacked
    this combat segment and no mandatory retreat is pending.

    Blocked while the active segment forbids routine phase advance (combat overlay segments).
    """
    from ..arc_segment import phase_advance_blocked

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
    raw = title_state.bucket(state).get("attacks_this_phase")
    if not isinstance(raw, list):
        return False
    attacked: set[str] = set()
    for uid in raw:
        if not isinstance(uid, str):
            continue
        u = state.board.units.get(uid)
        if u is not None and u.active and u.faction == faction:
            attacked.add(uid)
    return active_ids <= attacked


@bind_title_hook(AttackHook.ATTACK_PLAN_PREVIEW)
def attack_plan_preview(ctx: AttackPlanPreviewContext) -> dict[str, Any]:
    from ..combat_planning import compute_attack_plan_preview
    from hexengine.hexes.types import Hex

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
