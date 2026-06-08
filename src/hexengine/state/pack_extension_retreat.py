"""Read mandatory retreat steps from a title-owned GameState.extension bucket."""

from __future__ import annotations

from .game_state import GameState
from .engine_session_state import engine_read_session_state


def retreat_hexes_remaining(
    state: GameState, unit_id: str, *, session_state_key: str
) -> int | None:
    """Positive mandatory retreat steps left for unit_id, or None if none."""
    ob = engine_read_session_state(state, session_state_key).get("retreat_obligations")
    if not isinstance(ob, dict):
        return None
    raw = ob.get(unit_id)
    if raw is None:
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None
