"""Read mandatory retreat steps from a title-owned GameState.extension bucket."""

from __future__ import annotations

from .game_state import GameState
from .title_extension import title_bucket


def retreat_hexes_remaining(
    state: GameState, unit_id: str, *, extension_key: str
) -> int | None:
    """Positive mandatory retreat steps left for unit_id, or None if none."""
    ob = title_bucket(state, extension_key).get("retreat_obligations")
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
