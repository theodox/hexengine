"""
Hexdemo match-scoped session state in ``GameState.session_state``.

One pack id per session (`PACK_SESSION_STATE_KEY`). All reads of the hexdemo
bucket should go through ``bucket()`` so key layout stays in one place.
"""

from __future__ import annotations

from typing import Any

from hexengine.state import GameState
from hexengine.state.engine_session_state import (
    engine_read_session_state as _engine_read_session_state,
)

from ..constants import PACK_SESSION_STATE_KEY


def bucket(state: GameState) -> dict[str, Any]:
    """Copy of the hexdemo session-state bucket, or ``{}`` if absent."""

    if state.session_state_key == PACK_SESSION_STATE_KEY:
        return dict(state.session_state)
    return _engine_read_session_state(state, PACK_SESSION_STATE_KEY)


def attacks_this_phase(state: GameState) -> list[str]:
    """Unit ids that have already attacked in the current combat phase."""

    raw = bucket(state).get("attacks_this_phase")
    if not isinstance(raw, list):
        return []
    return [uid for uid in raw if isinstance(uid, str)]


def last_combat(state: GameState) -> dict[str, Any] | None:
    """Latest combat result payload from the session-state bucket, if present."""

    raw = bucket(state).get("last_combat")
    return dict(raw) if isinstance(raw, dict) else None


def retreat_obligations(state: GameState) -> dict[str, Any]:
    """Per-unit mandatory retreat steps remaining (unit id → steps)."""

    raw = bucket(state).get("retreat_obligations")
    return dict(raw) if isinstance(raw, dict) else {}


def advance_offer(state: GameState) -> dict[str, Any] | None:
    """Optional post-retreat advance window metadata (``faction``, …)."""

    raw = bucket(state).get("advance")
    return dict(raw) if isinstance(raw, dict) else None


def disrupt_instead_offered(state: GameState) -> bool:
    """True when optional disrupt-instead-of-retreat was offered for this combat."""

    return bool(bucket(state).get("disrupt_instead_offered"))


def retreat_hexes_remaining(state: GameState, unit_id: str) -> int | None:
    """Steps remaining for ``unit_id`` under the hexdemo extension bucket."""

    raw = retreat_obligations(state).get(unit_id)
    if raw is None:
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def any_retreat_obligation_pending(state: GameState) -> bool:
    """True if any unit still has a positive retreat obligation."""

    for v in retreat_obligations(state).values():
        try:
            if int(v) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def faction_has_pending_retreat(state: GameState, faction: str) -> bool:
    """True if ``faction`` owns any active unit with a positive retreat obligation."""

    for uid, v in retreat_obligations(state).items():
        try:
            if int(v) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        u = state.board.units.get(uid)
        if u is not None and u.active and u.faction == faction:
            return True
    return False


__all__ = [
    "advance_offer",
    "any_retreat_obligation_pending",
    "attacks_this_phase",
    "bucket",
    "disrupt_instead_offered",
    "faction_has_pending_retreat",
    "last_combat",
    "retreat_hexes_remaining",
    "retreat_obligations",
]
