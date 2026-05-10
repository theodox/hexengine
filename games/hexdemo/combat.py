"""
Hexdemo combat extension reads for ``GameState.extension[PACK_STATE_EXTENSION_KEY]``.

Server and client resolve obligations through optional ``GameDefinition`` hooks
on ``HexdemoGameDefinition``; per-unit steps are read from ``GameState`` via
``hexengine.state.pack_extension_retreat`` (shared with the browser client).
"""

from __future__ import annotations

from hexengine.state import GameState
from hexengine.state.pack_extension_retreat import retreat_hexes_remaining as _pack_steps

from .constants import PACK_STATE_EXTENSION_KEY


def retreat_hexes_remaining(state: GameState, unit_id: str) -> int | None:
    """Steps remaining for ``unit_id`` under the hexdemo extension bucket."""
    return _pack_steps(state, unit_id, extension_key=PACK_STATE_EXTENSION_KEY)


def any_retreat_obligation_pending(state: GameState) -> bool:
    """True if any unit still has a positive retreat obligation."""
    hx = state.extension.get(PACK_STATE_EXTENSION_KEY)
    if not isinstance(hx, dict):
        return False
    ob = hx.get("retreat_obligations")
    if not isinstance(ob, dict):
        return False
    for v in ob.values():
        try:
            if int(v) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def faction_has_pending_retreat(state: GameState, faction: str) -> bool:
    """True if ``faction`` owns any active unit with a positive retreat obligation."""
    hx = state.extension.get(PACK_STATE_EXTENSION_KEY)
    if not isinstance(hx, dict):
        return False
    ro = hx.get("retreat_obligations")
    if not isinstance(ro, dict):
        return False
    for uid, v in ro.items():
        try:
            if int(v) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        u = state.board.units.get(uid)
        if u is not None and u.active and u.faction == faction:
            return True
    return False
