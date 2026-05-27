"""
Hexdemo combat extension reads for the match title bucket.

Server and client resolve obligations through optional `GameDefinition` hooks
on `HexdemoGameDefinition`; per-unit steps use `hexengine.state.pack_extension_retreat`.
"""

from __future__ import annotations

from hexengine.state import GameState
from hexengine.state.pack_extension_retreat import (
    retreat_hexes_remaining as _pack_steps,
)

from .constants import PACK_STATE_EXTENSION_KEY
from .title_state import bucket


def retreat_hexes_remaining(state: GameState, unit_id: str) -> int | None:
    """Steps remaining for `unit_id` under the hexdemo extension bucket."""
    return _pack_steps(state, unit_id, extension_key=PACK_STATE_EXTENSION_KEY)


def any_retreat_obligation_pending(state: GameState) -> bool:
    """True if any unit still has a positive retreat obligation."""
    obligations = bucket(state).get("retreat_obligations")
    if not isinstance(obligations, dict):
        return False
    for v in obligations.values():
        try:
            if int(v) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def faction_has_pending_retreat(state: GameState, faction: str) -> bool:
    """True if `faction` owns any active unit with a positive retreat obligation."""
    pending_retreat = bucket(state).get("retreat_obligations")
    if not isinstance(pending_retreat, dict):
        return False
    for uid, v in pending_retreat.items():
        try:
            if int(v) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        u = state.board.units.get(uid)
        if u is not None and u.active and u.faction == faction:
            return True
    return False
