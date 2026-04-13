"""
Hooks for where markers may be placed or moved.

Game code can replace the rule on `hexengine.server.game_server.GameServer`
via `marker_placement_rule`. When that is `None`, the engine uses
`default_marker_destination_allowed` (any board hex with no active unit).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..hexes.types import Hex
from .game_state import GameState

MarkerPlacementRule = Callable[[GameState, dict[str, Any], Hex], bool]


def default_marker_destination_allowed(
    state: GameState, marker_wire: dict[str, Any], to_hex: Hex
) -> bool:
    """
    Return True if `to_hex` is on the board and has no active unit.

    `marker_wire` is the marker row dict (`id`, `type`, `position`, …);
    reserved for future rules (e.g. type-specific ranges).
    """
    _ = marker_wire
    if to_hex not in state.board.locations:
        return False
    return state.board.get_unit_at(to_hex) is None


def marker_destination_hexes_for_preview(
    state: GameState,
    marker_wire: dict[str, Any] | None,
    rule: MarkerPlacementRule | None,
) -> set[Hex]:
    """
    Hexes to highlight when dragging a marker (client preview).

    If `rule` is `None`, uses `default_marker_destination_allowed`.
    Custom server rules should eventually be mirrored client-side or pushed
    over the wire; until then previews match the default when rule is None.
    """
    eff: MarkerPlacementRule = (
        rule if rule is not None else default_marker_destination_allowed
    )
    out: set[Hex] = set()
    mw = marker_wire or {}
    for h in state.board.locations:
        if eff(state, mw, h):
            out.add(h)
    return out
