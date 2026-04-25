"""Read mandatory retreat steps from ``GameState.extension['hexdemo']``."""

from __future__ import annotations

from .game_state import GameState


def retreat_hexes_remaining(state: GameState, unit_id: str) -> int | None:
    """Positive mandatory retreat steps left for ``unit_id``, or ``None`` if none."""
    hx = state.extension.get("hexdemo")
    if not isinstance(hx, dict):
        return None
    ob = hx.get("retreat_obligations")
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
