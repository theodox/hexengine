"""
Hexdemo combat cleanup actions (title-owned arc structure).

Returns undoable ``StateAction`` lists for the engine combat-cleanup arc to execute.
Advance payload shape is a hexdemo convention; legality reads ``current_segment``.
"""

from __future__ import annotations

from typing import Any

from hexengine.hexes.math import distance
from hexengine.hexes.types import Hex
from hexengine.state import GameState
from hexengine.state.action_manager import StateAction
from hexengine.hooks.bucket import ApplyBucketPatch, BucketPatch
from hexengine.state.actions import (
    ClearUnitRetreatObligation,
    MoveUnit,
    PatchUnitAttributes,
)
from . import arc_segment, session_state


def _retreat_obligations_have_pending(ro: dict[str, Any]) -> bool:
    for v in ro.values():
        try:
            if int(v) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _advance_for_faction(
    state: GameState, player_faction: str, session_state_key: str
) -> dict[str, Any] | None:
    adv = session_state.advance_offer(state)
    if adv is None:
        return None
    if str(adv.get("faction", "")).strip() != str(player_faction).strip():
        return None
    return adv


def retreat_stack_unit_ids(
    state: GameState,
    from_hex: Hex,
    player_faction: str,
    uid_for_move: str,
) -> list[str]:
    """Unit ids that must retreat together from ``from_hex`` (includes ``uid_for_move``)."""

    faction = str(player_faction).strip()
    to_move: list[str] = []
    for u in state.board.active_units_at_hex(from_hex):
        if u.faction != faction:
            continue
        if session_state.retreat_hexes_remaining(state, u.unit_id) is None:
            continue
        to_move.append(u.unit_id)
    if uid_for_move not in to_move:
        to_move.append(uid_for_move)
    return to_move


def apply_retreat_fulfillment_step(
    state: GameState,
    session_state_key: str,
    player_faction: str,
    params: dict[str, Any],
) -> list[StateAction]:
    """Move a retreat stack (primary may already be at destination) and clear obligations."""

    uid = params.get("unit_id")
    if not isinstance(uid, str) or not uid.strip():
        return []
    fh, th = params.get("from_hex"), params.get("to_hex")
    if not isinstance(fh, dict) or not isinstance(th, dict):
        return []
    from_hex = Hex(int(fh["i"]), int(fh["j"]), int(fh["k"]))
    to_hex = Hex(int(th["i"]), int(th["j"]), int(th["k"]))

    to_move = retreat_stack_unit_ids(state, from_hex, player_faction, uid)
    actions: list[StateAction] = []
    for move_uid in to_move:
        u = state.board.units.get(move_uid)
        if u is None:
            continue
        if u.position == to_hex:
            continue
        if u.position != from_hex:
            raise ValueError(
                f"Unit {move_uid} is at {u.position}, expected {from_hex} or {to_hex}"
            )
        actions.append(MoveUnit(move_uid, from_hex=from_hex, to_hex=to_hex))
    for moved_uid in to_move:
        actions.append(ClearUnitRetreatObligation(moved_uid, session_state_key))
    return actions


def _defender_occupies_combat_hex(
    state: GameState, last: dict[str, Any], to_hex: Hex
) -> bool:
    """True when a defender from ``last_combat`` still actively holds the combat hex."""

    raw_ids = last.get("defender_ids")
    if isinstance(raw_ids, list) and raw_ids:
        defender_ids = [
            str(x).strip() for x in raw_ids if isinstance(x, str) and str(x).strip()
        ]
    else:
        did = str(last.get("defender_id", "")).strip()
        defender_ids = [did] if did else []
    for did in defender_ids:
        u = state.board.units.get(did)
        if u is not None and u.active and u.position == to_hex:
            return True
    return False


def maybe_open_advance_after_retreat(
    state: GameState, session_state_key: str
) -> list[StateAction]:
    """Open optional advance into the vacated defender hex when hexdemo rules match.

    Offered after defender retreat is resolved or when the defender was eliminated
    (``defender_destroyed`` or step-loss removal) and the combat hex is vacant.
    """

    hx = session_state.bucket(state)
    if not hx:
        return []
    if session_state.advance_offer(state) is not None:
        return []
    ro = session_state.retreat_obligations(state)
    if _retreat_obligations_have_pending(ro):
        return []
    last = session_state.last_combat(state)
    if last is None:
        return []

    outcome = str(last.get("outcome", "")).strip()
    if outcome not in ("defender_retreat", "defender_destroyed", "none"):
        return []

    attacker_id = str(last.get("attacker_id", "")).strip()
    if not attacker_id:
        return []
    raw_aids = last.get("attacker_ids")
    if isinstance(raw_aids, list) and raw_aids:
        attacker_ids = [
            str(x).strip() for x in raw_aids if isinstance(x, str) and str(x).strip()
        ]
    else:
        attacker_ids = [attacker_id]
    if not attacker_ids:
        return []

    d_hex = last.get("defender_hex")
    if not isinstance(d_hex, dict):
        return []
    try:
        to_hex = Hex(int(d_hex["i"]), int(d_hex["j"]), int(d_hex["k"]))
    except Exception:
        return []

    if _defender_occupies_combat_hex(state, last, to_hex):
        return []

    defender_id = str(last.get("defender_id", "")).strip()
    defender_faction: str | None = None
    if defender_id:
        d0 = state.board.units.get(defender_id)
        if d0 is not None:
            defender_faction = str(d0.faction)

    anchor_order = [attacker_id, *attacker_ids]
    seen: set[str] = set()
    a0 = None
    for aid in anchor_order:
        if not aid or aid in seen:
            continue
        seen.add(aid)
        au = state.board.units.get(aid)
        if au is None or not au.active:
            continue
        if defender_faction is not None and au.faction == defender_faction:
            continue
        if distance(au.position, to_hex) != 1:
            continue
        a0 = au
        break
    if a0 is None:
        return []

    from_hex = a0.position
    if any(True for _u in state.board.active_units_at_hex(to_hex)):
        return []

    unit_ids: list[str] = []
    for u in state.board.active_units_at_hex(from_hex):
        if u.active and u.faction == a0.faction:
            unit_ids.append(str(u.unit_id))
    if not unit_ids:
        return []

    return [
        ApplyBucketPatch(
            session_state_key,
            BucketPatch(
                values={
                    "advance": {
                        "schema": 1,
                        "faction": str(a0.faction),
                        "from_hex": {
                            "i": int(from_hex.i),
                            "j": int(from_hex.j),
                            "k": int(from_hex.k),
                        },
                        "to_hex": {
                            "i": int(to_hex.i),
                            "j": int(to_hex.j),
                            "k": int(to_hex.k),
                        },
                        "unit_ids": list(sorted(set(unit_ids))),
                    },
                }
            ),
        )
    ]


def is_combat_advance_move(
    state: GameState, params: dict[str, Any], player_faction: str, session_state_key: str
) -> bool:
    """True when this ``MoveUnit`` wire matches the pending advance into the vacated hex."""

    adv = _advance_for_faction(state, player_faction, session_state_key)
    if adv is None:
        return False
    to_hex_raw = adv.get("to_hex")
    unit_ids_raw = adv.get("unit_ids")
    if not (
        isinstance(to_hex_raw, dict)
        and isinstance(unit_ids_raw, list)
        and isinstance(params.get("unit_id"), str)
        and isinstance(params.get("to_hex"), dict)
    ):
        return False
    try:
        adv_to = Hex(
            int(to_hex_raw["i"]),
            int(to_hex_raw["j"]),
            int(to_hex_raw["k"]),
        )
    except Exception:
        return False
    try:
        req_to = Hex(**params["to_hex"])
    except Exception:
        return False
    uid = str(params["unit_id"]).strip()
    allowed_ids = {str(x) for x in unit_ids_raw if isinstance(x, str)}
    return bool(uid and req_to == adv_to and uid in allowed_ids)


def disrupt_instead_of_retreat(
    state: GameState, session_state_key: str, player_faction: str
) -> list[StateAction]:
    """Disrupt retreating units and clear obligations for ``player_faction``."""

    if not session_state.bucket(state):
        raise ValueError("No title combat extension")
    if not arc_segment.segment_allows(
        state, player_faction, "CombatDisruptInsteadOfRetreat"
    ):
        raise ValueError(
            "Disrupt-instead is only allowed during the retreat-or-disrupt gate"
        )
    ro = dict(session_state.retreat_obligations(state))

    actions: list[StateAction] = []
    cleared_any = False
    faction = str(player_faction).strip()
    for uid in list(ro.keys()):
        raw = ro.get(uid)
        try:
            n = int(raw)
        except (TypeError, ValueError):
            continue
        if n <= 0:
            continue
        u = state.board.units.get(str(uid))
        if u is None or not u.active or u.faction != faction:
            continue
        actions.append(PatchUnitAttributes(str(uid), {"disrupted": True}))
        ro.pop(uid, None)
        cleared_any = True
    if not cleared_any:
        raise ValueError("No retreat obligation found for this faction")

    remove: tuple[str, ...] = ()
    if not _retreat_obligations_have_pending(ro):
        remove = ("disrupt_instead_offered",)
    actions.append(
        ApplyBucketPatch(
            session_state_key,
            BucketPatch(values={"retreat_obligations": ro}, remove_keys=remove),
        )
    )
    return actions


def clear_advance_gate(state: GameState, session_state_key: str) -> list[StateAction]:
    """Skip a pending advance: drop the advance payload (no unit moves)."""

    faction = str(state.turn.current_faction).strip()
    if not arc_segment.segment_allows(state, faction, "CombatDeclineAdvance"):
        return []
    if session_state.advance_offer(state) is None:
        return []
    return [
        ApplyBucketPatch(
            session_state_key,
            BucketPatch(values={}, remove_keys=("advance",)),
        )
    ]


def resolve_combat_advance(
    state: GameState, session_state_key: str, player_faction: str
) -> list[StateAction]:
    """Move advancing stack into vacated hex and clear the advance offer."""

    if not session_state.bucket(state):
        raise ValueError("No title combat extension")
    adv = _advance_for_faction(state, player_faction, session_state_key)
    if adv is None:
        raise ValueError("No advance pending")
    to_hex_raw = adv.get("to_hex")
    if not isinstance(to_hex_raw, dict):
        raise ValueError("Invalid to_hex")
    try:
        to_hex = Hex(int(to_hex_raw["i"]), int(to_hex_raw["j"]), int(to_hex_raw["k"]))
    except Exception as e:
        raise ValueError("Invalid to_hex") from e
    unit_ids_raw = adv.get("unit_ids")
    if not isinstance(unit_ids_raw, list) or not unit_ids_raw:
        raise ValueError("No units to advance")

    faction = str(player_faction).strip()
    actions: list[StateAction] = []
    for uid in unit_ids_raw:
        if not isinstance(uid, str) or not uid.strip():
            continue
        u = state.board.units.get(uid)
        if u is None or not u.active or u.faction != faction:
            continue
        actions.append(MoveUnit(uid, from_hex=u.position, to_hex=to_hex))
    actions.append(
        ApplyBucketPatch(
            session_state_key,
            BucketPatch(values={}, remove_keys=("advance",)),
        )
    )
    return actions


__all__ = [
    "clear_advance_gate",
    "disrupt_instead_of_retreat",
    "is_combat_advance_move",
    "maybe_open_advance_after_retreat",
    "resolve_combat_advance",
]
