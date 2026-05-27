"""
Engine logic for opening the post-retreat combat advance gate.

Titles override via `AttackHooks.on_retreat_obligation_cleared` (or legacy
`maybe_open_combat_advance_after_retreat`); when that returns `ENGINE_DEFAULT`,
`GameServer` uses `default_maybe_open_combat_advance_after_retreat`.
"""

from __future__ import annotations

from ...hexes.math import distance
from ...hexes.types import Hex
from ...state import GameState
from ...state.actions import OpenCombatAdvance


def default_maybe_open_combat_advance_after_retreat(
    state: GameState,
    extension_key: str,
) -> OpenCombatAdvance | None:
    """Return an `OpenCombatAdvance` action if the engine advance gate should open.

    After retreat obligations are cleared, open an optional advance gate when:

    - last combat outcome was `defender_retreat`
    - the original defender hex is now empty
    - at least one active attacker from `last_combat.attacker_ids` is cube-adjacent
      to that hex (so combined / ranged attacks still allow advance from the melee stack)
    """

    hx = state.extension.get(extension_key)
    if not isinstance(hx, dict):
        return None
    if str(hx.get("combat_gate", "")).strip():
        return None
    last = hx.get("last_combat")
    if not isinstance(last, dict):
        return None
    if str(last.get("outcome", "")).strip() != "defender_retreat":
        return None

    attacker_id = str(last.get("attacker_id", "")).strip()
    defender_id = str(last.get("defender_id", "")).strip()
    if not attacker_id or not defender_id:
        return None
    raw_aids = last.get("attacker_ids")
    if isinstance(raw_aids, list) and raw_aids:
        attacker_ids = [
            str(x).strip() for x in raw_aids if isinstance(x, str) and str(x).strip()
        ]
    else:
        attacker_ids = [attacker_id] if attacker_id else []
    if not attacker_ids:
        return None

    d_hex = last.get("defender_hex")
    if not isinstance(d_hex, dict):
        return None
    try:
        to_hex = Hex(int(d_hex["i"]), int(d_hex["j"]), int(d_hex["k"]))
    except Exception:
        return None

    d0 = state.board.units.get(defender_id)
    if d0 is None:
        return None

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
        return None

    from_hex = a0.position
    if any(True for _u in state.board.active_units_at_hex(to_hex)):
        return None

    unit_ids: list[str] = []
    for u in state.board.active_units_at_hex(from_hex):
        if u.active and u.faction == a0.faction:
            unit_ids.append(str(u.unit_id))
    if not unit_ids:
        return None

    return OpenCombatAdvance(
        extension_key,
        advancing_faction=str(a0.faction),
        from_hex=from_hex,
        to_hex=to_hex,
        unit_ids=tuple(sorted(set(unit_ids))),
    )


__all__ = ["default_maybe_open_combat_advance_after_retreat"]
