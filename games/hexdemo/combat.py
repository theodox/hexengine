"""
Hexdemo combat extension reads for the match title bucket.

Server and client resolve obligations through title movement hooks; per-unit
steps use `hexengine.state.pack_extension_retreat` with `PACK_STATE_EXTENSION_KEY`.
"""

from __future__ import annotations

from hexengine.state import GameState
from hexengine.state.pack_extension_retreat import (
    retreat_hexes_remaining as _pack_steps,
)

from . import title_state
from .constants import PACK_STATE_EXTENSION_KEY


def retreat_hexes_remaining(state: GameState, unit_id: str) -> int | None:
    """Steps remaining for `unit_id` under the hexdemo extension bucket."""
    return _pack_steps(state, unit_id, extension_key=PACK_STATE_EXTENSION_KEY)


def any_retreat_obligation_pending(state: GameState) -> bool:
    """True if any unit still has a positive retreat obligation."""
    for v in title_state.retreat_obligations(state).values():
        try:
            if int(v) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def faction_has_pending_retreat(state: GameState, faction: str) -> bool:
    """True if `faction` owns any active unit with a positive retreat obligation."""
    for uid, v in title_state.retreat_obligations(state).items():
        try:
            if int(v) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        u = state.board.units.get(uid)
        if u is not None and u.active and u.faction == faction:
            return True
    return False
