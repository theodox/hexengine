"""
Hexdemo combat cleanup actions (title-owned arc structure).

Returns undoable ``StateAction`` lists for the engine combat-cleanup arc to execute.
Gate string literals and advance payload shape are hexdemo conventions only.
"""

from __future__ import annotations

from typing import Any

from hexengine.hexes.math import distance
from hexengine.hexes.types import Hex
from hexengine.state import GameState
from hexengine.state.action_manager import StateAction
from hexengine.state.actions import (
    ClearUnitRetreatObligation,
    MoveUnit,
    PatchTitleBucket,
    PatchUnitAttributes,
)
from hexengine.state.title_extension import title_bucket

# Must match ``combat_transitions`` gate constants (avoid import cycle).
GATE_AWAITING_ADVANCE = "awaiting_advance"
GATE_AWAITING_RETREAT_OR_DISRUPT = "awaiting_retreat_or_disrupt"


def _retreat_obligations_have_pending(ro: dict[str, Any]) -> bool:
    for v in ro.values():
        try:
            if int(v) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def retreat_stack_unit_ids(
    state: GameState,
    from_hex: Hex,
    player_faction: str,
    uid_for_move: str,
) -> list[str]:
    """Unit ids that must retreat together from ``from_hex`` (includes ``uid_for_move``)."""

    from . import combat

    faction = str(player_faction).strip()
    to_move: list[str] = []
    for u in state.board.active_units_at_hex(from_hex):
        if u.faction != faction:
            continue
        if combat.retreat_hexes_remaining(state, u.unit_id) is None:
            continue
        to_move.append(u.unit_id)
    if uid_for_move not in to_move:
        to_move.append(uid_for_move)
    return to_move


def apply_retreat_fulfillment_step(
    state: GameState,
    extension_key: str,
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
        actions.append(ClearUnitRetreatObligation(moved_uid, extension_key))
    ro_after = dict(title_bucket(state, extension_key).get("retreat_obligations") or {})
    for moved_uid in to_move:
        ro_after.pop(moved_uid, None)
    if not _retreat_obligations_have_pending(ro_after):
        if str(title_bucket(state, extension_key).get("combat_gate", "")).strip():
            actions.append(
                PatchTitleBucket(extension_key, {}, remove_keys=("combat_gate",))
            )
    return actions


def maybe_open_advance_after_retreat(
    state: GameState, extension_key: str
) -> list[StateAction]:
    """Open optional post-retreat advance when hexdemo rules match."""

    hx = title_bucket(state, extension_key)
    if not hx:
        return []
    if str(hx.get("combat_gate", "")).strip():
        return []
    last = hx.get("last_combat")
    if not isinstance(last, dict):
        return []
    if str(last.get("outcome", "")).strip() != "defender_retreat":
        return []

    attacker_id = str(last.get("attacker_id", "")).strip()
    defender_id = str(last.get("defender_id", "")).strip()
    if not attacker_id or not defender_id:
        return []
    raw_aids = last.get("attacker_ids")
    if isinstance(raw_aids, list) and raw_aids:
        attacker_ids = [
            str(x).strip() for x in raw_aids if isinstance(x, str) and str(x).strip()
        ]
    else:
        attacker_ids = [attacker_id] if attacker_id else []
    if not attacker_ids:
        return []

    d_hex = last.get("defender_hex")
    if not isinstance(d_hex, dict):
        return []
    try:
        to_hex = Hex(int(d_hex["i"]), int(d_hex["j"]), int(d_hex["k"]))
    except Exception:
        return []

    d0 = state.board.units.get(defender_id)
    if d0 is None:
        return []

    anchor_order = [attacker_id, *attacker_ids]
    seen: set[str] = set()
    a0 = None
    for aid in anchor_order:
        if not aid or aid in seen:
            continue
        seen.add(aid)
        au = state.board.units.get(aid)
        if au is None or not au.active or au.faction == d0.faction:
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
        PatchTitleBucket(
            extension_key,
            {
                "combat_gate": GATE_AWAITING_ADVANCE,
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
            },
        )
    ]


def is_combat_advance_move(
    state: GameState, params: dict[str, Any], player_faction: str, extension_key: str
) -> bool:
    """True when this ``MoveUnit`` wire matches the pending advance into the vacated hex."""

    hx_adv = title_bucket(state, extension_key)
    if not hx_adv:
        return False
    if str(hx_adv.get("combat_gate", "")).strip() != GATE_AWAITING_ADVANCE:
        return False
    adv = hx_adv.get("advance")
    if not isinstance(adv, dict) or str(adv.get("faction", "")).strip() != str(
        player_faction
    ):
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
    state: GameState, extension_key: str, player_faction: str
) -> list[StateAction]:
    """Disrupt retreating units and clear obligations for ``player_faction``."""

    hx0 = title_bucket(state, extension_key)
    if not hx0:
        raise ValueError("No title combat extension")
    gate = str(hx0.get("combat_gate", "")).strip()
    if gate != GATE_AWAITING_RETREAT_OR_DISRUPT:
        raise ValueError(
            "Disrupt-instead is only allowed when combat_gate is awaiting_retreat_or_disrupt"
        )
    prev_ro = hx0.get("retreat_obligations")
    ro = dict(prev_ro) if isinstance(prev_ro, dict) else {}

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
        remove = ("combat_gate",)
    actions.append(
        PatchTitleBucket(
            extension_key,
            {"retreat_obligations": ro},
            remove_keys=remove,
        )
    )
    return actions


def clear_advance_gate(state: GameState, extension_key: str) -> list[StateAction]:
    """Skip a pending advance: drop the advance payload and gate (no unit moves)."""

    hx0 = title_bucket(state, extension_key)
    if not hx0:
        return []
    if str(hx0.get("combat_gate", "")).strip() != GATE_AWAITING_ADVANCE:
        return []
    return [
        PatchTitleBucket(
            extension_key,
            {},
            remove_keys=("advance", "combat_gate"),
        )
    ]


def resolve_combat_advance(
    state: GameState, extension_key: str, player_faction: str
) -> list[StateAction]:
    """Move advancing stack into vacated hex and clear the advance gate."""

    hx0 = title_bucket(state, extension_key)
    if not hx0:
        raise ValueError("No title combat extension")
    if str(hx0.get("combat_gate", "")).strip() != GATE_AWAITING_ADVANCE:
        raise ValueError("No advance pending")
    adv = hx0.get("advance")
    if not isinstance(adv, dict):
        raise ValueError("Missing advance payload")
    faction = str(player_faction).strip()
    if str(adv.get("faction", "")).strip() != faction:
        raise ValueError("Not allowed to advance for this faction")
    to_hex_raw = adv.get("to_hex")
    if not isinstance(to_hex_raw, dict):
        raise ValueError("Invalid to_hex")
    try:
        to_hex = Hex(
            int(to_hex_raw["i"]), int(to_hex_raw["j"]), int(to_hex_raw["k"])
        )
    except Exception as e:
        raise ValueError("Invalid to_hex") from e
    unit_ids_raw = adv.get("unit_ids")
    if not isinstance(unit_ids_raw, list) or not unit_ids_raw:
        raise ValueError("No units to advance")

    actions: list[StateAction] = []
    for uid in unit_ids_raw:
        if not isinstance(uid, str) or not uid.strip():
            continue
        u = state.board.units.get(uid)
        if u is None or not u.active or u.faction != faction:
            continue
        actions.append(MoveUnit(uid, from_hex=u.position, to_hex=to_hex))
    actions.append(
        PatchTitleBucket(
            extension_key,
            {},
            remove_keys=("advance", "combat_gate"),
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
