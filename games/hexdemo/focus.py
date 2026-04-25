"""Post-sync UI focus hints (which unit the browser client should select for this viewer)."""

from __future__ import annotations

from hexengine.state import GameState
from hexengine.state.hexdemo_retreat import retreat_hexes_remaining


def focus_unit_id_after_state_sync(
    state: GameState, viewer_faction: str | None
) -> str | None:
    """
    When exactly one active unit on ``viewer_faction`` owes a mandatory retreat,
    return its id so the client can select it (visible marker + retreat drag UX).
    """
    if not viewer_faction:
        return None
    fac = viewer_faction
    obligated = sorted(
        uid
        for uid, u in state.board.units.items()
        if u.active
        and u.faction == fac
        and retreat_hexes_remaining(state, uid) is not None
    )
    if len(obligated) != 1:
        return None
    return obligated[0]
