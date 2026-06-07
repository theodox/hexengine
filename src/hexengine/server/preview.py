"""
Authoritative drag-preview hex sets (unit move / retreat, marker placement).

Thin clients request previews via WebSocket; they must not call
``compute_valid_moves`` locally. This module mirrors the gates in
``GameServer._validate_move_unit_request`` for normal moves and retreats.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ..hexes.math import distance, neighbors
from ..hexes.types import Hex
from ..hooks.core import ENGINE_DEFAULT
from ..state import GameState
from ..state.logic import (
    compute_reachable_hexes,
    compute_valid_moves,
    is_valid_move,
)
from ..state.phase_rules import phase_allows_unit_move


def hexes_to_wire(rows: Iterable[Hex]) -> list[dict[str, int]]:
    return [
        {"i": int(h.i), "j": int(h.j), "k": int(h.k)}
        for h in sorted(rows, key=lambda x: (x.i, x.j, x.k))
    ]


@dataclass(frozen=True, slots=True)
class UnitDragPreview:
    """Wire-oriented unit drag preview (``unit_preview`` message)."""

    kind: str
    hexes: list[dict[str, int]]
    through_hexes: list[dict[str, int]] | None = None


def compute_unit_drag_preview(
    *,
    state: GameState,
    unit_id: str,
    player_faction: str,
    board_hexes: list[Hex],
    retreat_hexes_remaining: Callable[[GameState, str], int | None],
    faction_has_pending_retreat: Callable[[GameState, str], bool],
    movement_budget_for_unit: Callable[[GameState, str], float],
    zoc_hexes_for_unit: Callable[[GameState, str], frozenset[Hex] | None],
    max_active_units_per_hex: Callable[[GameState, str], int | None],
    movement_step_cost_fn: Callable[
        [str], Callable[[GameState, str, Hex, Hex, float], float]
    ],
    retreat_blocked_hexes: Callable[[GameState, str], frozenset[Hex] | None | object],
) -> UnitDragPreview:
    """
    Legal destination hexes for an in-progress unit drag.

    Returns empty ``hexes`` when the title/server gates disallow moving (e.g. pending
    retreat on another unit, wrong phase).
    """
    u = state.board.units.get(unit_id)
    if u is None or not u.active:
        return UnitDragPreview(kind="move", hexes=[])

    rem = retreat_hexes_remaining(state, unit_id)
    if rem is None:
        if faction_has_pending_retreat(state, player_faction):
            return UnitDragPreview(kind="move", hexes=[])
        if not phase_allows_unit_move(state.turn.current_phase):
            return UnitDragPreview(kind="move", hexes=[])
        budget = movement_budget_for_unit(state, unit_id)
        zoc = zoc_hexes_for_unit(state, unit_id)
        max_stack = max_active_units_per_hex(state, unit_id)
        step_fn = movement_step_cost_fn(unit_id)
        valid = compute_valid_moves(
            state,
            unit_id,
            budget,
            zoc_hexes=zoc,
            blocked_hexes=None,
            max_active_units_per_hex=max_stack,
            step_cost=step_fn,
        )
        start_h = u.position
        footprint = frozenset(board_hexes) | {start_h} | frozenset(neighbors(start_h))
        out = [h for h in valid if h in footprint]
        return UnitDragPreview(kind="move", hexes=hexes_to_wire(out))

    budget = float(rem)
    blocked_raw = retreat_blocked_hexes(state, unit_id)
    if blocked_raw is ENGINE_DEFAULT or blocked_raw is None:
        blocked_hexes = None
    else:
        blocked_hexes = (
            blocked_raw
            if isinstance(blocked_raw, frozenset)
            else frozenset(blocked_raw)
        )
    max_stack = max_active_units_per_hex(state, unit_id)
    step_fn = movement_step_cost_fn(unit_id)
    start = u.position
    reachable = compute_reachable_hexes(
        state,
        start,
        budget,
        moving_faction=u.faction,
        zoc_hexes=None,
        blocked_hexes=blocked_hexes,
        max_active_units_per_hex=max_stack,
        step_cost=step_fn,
    )
    end_hexes: list[Hex] = []
    through_hexes: list[Hex] = []
    for h in reachable.keys():
        if any(x.faction != player_faction for x in state.board.active_units_at_hex(h)):
            continue
        if (
            max_stack is not None
            and len(state.board.active_units_at_hex(h)) >= max_stack
        ):
            continue
        if h != start:
            through_hexes.append(h)
        if distance(start, h) != rem:
            continue
        if is_valid_move(
            state,
            unit_id,
            h,
            budget,
            zoc_hexes=None,
            blocked_hexes=blocked_hexes,
            max_active_units_per_hex=max_stack,
            step_cost=step_fn,
        ):
            end_hexes.append(h)
    return UnitDragPreview(
        kind="retreat",
        hexes=hexes_to_wire(end_hexes),
        through_hexes=hexes_to_wire(through_hexes),
    )


def compute_marker_drag_preview(
    *,
    state: GameState,
    marker_wire: dict[str, object],
    board_hexes: Iterable[Hex],
    destination_allowed: Callable[[GameState, dict[str, object], Hex], bool],
) -> list[dict[str, int]]:
    """Legal marker drop hexes for an in-progress marker drag."""
    out: list[Hex] = []
    for h in board_hexes:
        if destination_allowed(state, marker_wire, h):
            out.append(h)
    return hexes_to_wire(out)


__all__ = [
    "UnitDragPreview",
    "compute_marker_drag_preview",
    "compute_unit_drag_preview",
    "hexes_to_wire",
]
