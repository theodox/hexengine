"""
Game logic utilities for computing state-derived information.

These are pure functions that compute things like valid moves,
line of sight, etc. from game state without modifying it.
"""

from __future__ import annotations

import heapq

from ..hexes.math import distance, neighbors
from ..hexes.types import Hex
from ..state.game_state import GameState

# Default path-cost budget when `hexengine.gamedef.protocol.GameDefinition`
# does not implement `movement_budget_for_unit`.
DEFAULT_MOVEMENT_BUDGET = 4.0


def adjacent_enemy_zoc_hexes(state: GameState, unit_id: str) -> frozenset[Hex]:
    """
    Hexes cube-adjacent to any active enemy unit (relative to ``unit_id``'s faction).

    Titles can expose this via ``GameDefinition.zoc_hexes_for_unit`` for stop-on-ZOC
    movement (see :func:`compute_reachable_hexes`).
    """
    unit = state.board.units.get(unit_id)
    if unit is None or not unit.active:
        return frozenset()
    faction = unit.faction
    out: set[Hex] = set()
    for u in state.board.units.values():
        if not u.active or u.faction == faction:
            continue
        for h in neighbors(u.position):
            out.add(h)
    return frozenset(out)


def adjacent_friendly_zoc_hexes(state: GameState, unit_id: str) -> frozenset[Hex]:
    """
    Hexes cube-adjacent to any active friendly unit (relative to ``unit_id``'s faction).

    Useful for rules that treat friendly ZOC as "cover" against enemy ZOC effects.
    """
    unit = state.board.units.get(unit_id)
    if unit is None or not unit.active:
        return frozenset()
    faction = unit.faction
    out: set[Hex] = set()
    for u in state.board.units.values():
        if not u.active or u.faction != faction or u.unit_id == unit_id:
            continue
        for h in neighbors(u.position):
            out.add(h)
    return frozenset(out)


def retreat_impassable_enemy_zoc_hexes(
    state: GameState,
    unit_id: str,
    *,
    enemy_zoc_ring: frozenset[Hex] | None = None,
) -> frozenset[Hex]:
    """
    Hexes a mandatory retreat may not enter or pass through: enemy ZOC ring minus any
    overlap with friendly ZOC (same overlap rule as server retreat validation).

    When ``enemy_zoc_ring`` is ``None``, uses :func:`adjacent_enemy_zoc_hexes` (so thin
    clients without a title ``zoc_hexes_for_unit`` still match authoritative routing).
    """
    enemy = (
        adjacent_enemy_zoc_hexes(state, unit_id)
        if enemy_zoc_ring is None
        else enemy_zoc_ring
    )
    friendly = adjacent_friendly_zoc_hexes(state, unit_id)
    return frozenset(h for h in enemy if h not in friendly)


def compute_reachable_hexes(
    state: GameState,
    start_hex: Hex,
    max_cost: float,
    *,
    zoc_hexes: frozenset[Hex] | None = None,
    blocked_hexes: frozenset[Hex] | None = None,
) -> dict[Hex, float]:
    """Calculate all hexes reachable from start_hex within max_cost.

    Uses Dijkstra's algorithm to find the minimum cost path to each reachable hex.
    Takes into account terrain costs and occupied hexes.

    Args:
        state: Current game state
        start_hex: Starting hex position
        max_cost: Maximum movement cost budget
        zoc_hexes: If set, stop-on-ZOC-entry: do not expand from any hex in this set
            except ``start_hex`` (first ZOC entered ends the move).
        blocked_hexes: If set, treat these hexes as impassable for purposes of reachability,
            except ``start_hex`` (allows retreating out of contact even if the unit starts
            in a blocked hex).

    Returns:
        Dictionary mapping reachable hexes to their minimum cost from start_hex
    """
    # Dictionary to store the minimum cost to reach each hex
    costs = {start_hex: 0.0}

    # Priority queue: (cost, counter, hex)
    # Counter is used as a tie-breaker to avoid comparing hex objects
    counter = 0
    heap = [(0.0, counter, start_hex)]

    while heap:
        current_cost, _, current_hex = heapq.heappop(heap)

        # Skip if we've already found a better path to this hex
        if current_cost > costs.get(current_hex, float("inf")):
            continue

        # Hard blocks: cannot traverse through these hexes, but allow the start hex so a
        # unit can still leave contact.
        if (
            blocked_hexes is not None
            and current_hex in blocked_hexes
            and current_hex != start_hex
        ):
            continue

        # Stop-on-ZOC-entry: cannot leave a ZOC hex in the same move (except from start).
        if (
            zoc_hexes is not None
            and current_hex in zoc_hexes
            and current_hex != start_hex
        ):
            continue

        # Explore all neighboring hexes
        for neighbor in neighbors(current_hex):
            if (
                blocked_hexes is not None
                and neighbor in blocked_hexes
                and neighbor != start_hex
            ):
                continue
            # Calculate cost to move to this neighbor
            neighbor_terrain_cost = state.board.get_movement_cost(neighbor)

            # Skip if impassable
            if neighbor_terrain_cost == float("inf"):
                continue

            new_cost = current_cost + neighbor_terrain_cost

            # Only process if within budget and not occupied
            if new_cost <= max_cost and not state.board.is_occupied(neighbor):
                # If this is a better path to the neighbor, update it
                if new_cost < costs.get(neighbor, float("inf")):
                    costs[neighbor] = new_cost
                    counter += 1
                    heapq.heappush(heap, (new_cost, counter, neighbor))

    return costs


def compute_valid_moves(
    state: GameState,
    unit_id: str,
    movement_budget: float,
    *,
    zoc_hexes: frozenset[Hex] | None = None,
    blocked_hexes: frozenset[Hex] | None = None,
) -> set[Hex]:
    """Compute valid movement hexes for a unit.

    Args:
        state: Current game state
        unit_id: ID of the unit to compute moves for
        movement_budget: Maximum movement cost available
        zoc_hexes: Optional zone-of-control set for stop-on-entry (see
            :func:`compute_reachable_hexes`).
        blocked_hexes: Optional impassable hex set (see :func:`compute_reachable_hexes`).

    Returns:
        Set of hexes the unit can legally move to
    """
    unit = state.board.units.get(unit_id)
    if unit is None or not unit.active:
        return set()

    reachable = compute_reachable_hexes(
        state,
        unit.position,
        movement_budget,
        zoc_hexes=zoc_hexes,
        blocked_hexes=blocked_hexes,
    )

    # Return just the hexes (not the costs)
    return set(reachable.keys())


def is_valid_move(
    state: GameState,
    unit_id: str,
    target_hex: Hex,
    movement_budget: float,
    *,
    zoc_hexes: frozenset[Hex] | None = None,
    blocked_hexes: frozenset[Hex] | None = None,
) -> bool:
    """Check if a specific move is valid.

    Args:
        state: Current game state
        unit_id: ID of the unit to move
        target_hex: Target hex position
        movement_budget: Maximum movement cost available
        zoc_hexes: Optional ZOC set (same semantics as :func:`compute_valid_moves`).
        blocked_hexes: Optional impassable hex set (same semantics as :func:`compute_valid_moves`).

    Returns:
        True if the move is valid, False otherwise
    """
    return target_hex in compute_valid_moves(
        state,
        unit_id,
        movement_budget,
        zoc_hexes=zoc_hexes,
        blocked_hexes=blocked_hexes,
    )


def compute_retreat_destination_hexes(
    state: GameState,
    unit_id: str,
    required_steps: int,
    movement_budget: float,
    *,
    zoc_hexes: frozenset[Hex] | None = None,
    blocked_hexes: frozenset[Hex] | None = None,
) -> set[Hex]:
    """
    Hexes reachable as a retreat fulfillment: graph reachability within budget and
    cube distance from the unit's current hex exactly equals ``required_steps``.

    When ``zoc_hexes`` is passed, applies the same stop-on-entry rule as normal movement.
    Callers may pass ``None`` for mandatory retreat so multi-hex paths stay legal.
    When ``blocked_hexes`` is passed, treats those hexes as impassable (except start).
    """
    unit = state.board.units.get(unit_id)
    if unit is None or not unit.active:
        return set()
    start = unit.position
    reachable = compute_reachable_hexes(
        state,
        start,
        movement_budget,
        zoc_hexes=zoc_hexes,
        blocked_hexes=blocked_hexes,
    )
    out: set[Hex] = set()
    for h in reachable:
        if distance(start, h) == required_steps and is_valid_move(
            state,
            unit_id,
            h,
            movement_budget,
            zoc_hexes=zoc_hexes,
            blocked_hexes=blocked_hexes,
        ):
            out.add(h)
    return out
