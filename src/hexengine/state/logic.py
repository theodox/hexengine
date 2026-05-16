"""
Game logic utilities for computing state-derived information.

These are pure functions that compute things like valid moves,
line of sight, etc. from game state without modifying it.
"""

from __future__ import annotations

import heapq
from collections.abc import Callable

from ..hexes.constants import PI_OVER_6
from ..hexes.math import distance, neighbors
from ..hexes.shapes import angular_sector_hexes, hex_line_segment
from ..hexes.types import Hex
from ..state.game_state import GameState
from .map_feature_queries import edge_line_of_sight_blocks_hex_line

# Default path-cost budget when hexengine.gamedef.protocol.GameDefinition
# does not implement movement_budget_for_unit.
DEFAULT_MOVEMENT_BUDGET = 4.0


def get_blocking_hexes(state: GameState, a: Hex, b: Hex) -> tuple[Hex, ...]:
    """
    Hexes which block line of sight between a and b.

    Current rule: terrain blocks LOS when LocationState.block_los is True.
    Only intermediate hexes are considered blocking; endpoints never block LOS.
    """
    segment = list(hex_line_segment(a, b))
    if len(segment) <= 2:
        return ()
    out: list[Hex] = []
    for h in segment[1:-1]:
        loc = state.board.effective_location(h)
        if loc is not None and bool(getattr(loc, "block_los", True)):
            out.append(h)
    return tuple(out)


def has_line_of_sight(state: GameState, a: Hex, b: Hex) -> bool:
    """True when there are no LOS-blocking intermediate hexes or blocking edge tags."""
    if get_blocking_hexes(state, a, b):
        return False
    if edge_line_of_sight_blocks_hex_line(state.board, a, b):
        return False
    return True


def los_visible_hexes_in_cone(
    state: GameState,
    origin: Hex,
    max_distance: int,
    *,
    direction: int,
    half_angle: float = PI_OVER_6,
) -> set[Hex]:
    """
    Hexes within a directional cone from origin which are also line-of-sight visible.

    Candidate-shape + LOS filter helper for titles (e.g. ranged attacks):

    - The cone is defined by direction (0..5) and half_angle around that centerline.
      Default half_angle=PI_OVER_6 yields a 60° cone (±30°) aligned to hex sides.
    - Returned hexes are within cube distance <= max_distance and include origin.
    - LOS is tested against LocationState.block_los using has_line_of_sight.
      Endpoints do not block LOS; only intermediate hexes are blockers.
    """
    max_d = int(max_distance)
    if max_d < 0:
        return set()

    out: set[Hex] = set()
    for h in angular_sector_hexes(
        origin, max_d, direction=int(direction), half_angle=float(half_angle)
    ):
        if has_line_of_sight(state, origin, h):
            out.add(h)
    return out


def adjacent_enemy_zoc_hexes(state: GameState, unit_id: str) -> frozenset[Hex]:
    """
    Hexes cube-adjacent to any active enemy unit (relative to unit_id's faction).

    Titles can expose this via GameDefinition.zoc_hexes_for_unit for stop-on-ZOC
    movement (see compute_reachable_hexes).
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
    Hexes cube-adjacent to any active friendly unit (relative to unit_id's faction).

    Useful for rules that treat friendly ZOC as cover against enemy ZOC effects.
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

    When enemy_zoc_ring is None, uses adjacent_enemy_zoc_hexes (so thin clients without a
    title zoc_hexes_for_unit still match authoritative routing).
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
    moving_faction: str | None = None,
    zoc_hexes: frozenset[Hex] | None = None,
    blocked_hexes: frozenset[Hex] | None = None,
    max_active_units_per_hex: int | None = None,
    step_cost: Callable[[GameState, Hex, Hex, float], float] | None = None,
) -> dict[Hex, float]:
    """Calculate all hexes reachable from start_hex within max_cost.

    Uses Dijkstra's algorithm to find the minimum cost path to each reachable hex.
    Takes into account terrain costs and occupied hexes.

    state: current game state. start_hex: starting hex position. max_cost: maximum movement
    cost budget.

    moving_faction: when set, occupied hexes are passable only when every active unit on
    that hex belongs to moving_faction.

    zoc_hexes: if set, stop-on-ZOC-entry; do not expand from any hex in this set except
    start_hex (first ZOC entered ends the move).

    blocked_hexes: if set, treat these hexes as impassable except start_hex (allows
    retreating out of contact even if the unit starts in a blocked hex).

    max_active_units_per_hex: when set, allows ending a move on a hex with fewer than this
    many active units. A unit may still traverse through friendly-occupied hexes (paying
    normal terrain cost) as long as moving_faction is set and the hex is friendly-occupied.

    step_cost: when set, called as (state, from_hex, to_hex, destination_terrain_cost) and
    must return the total movement cost for that neighbor step (inf = impassable). When
    omitted, each step costs destination_terrain_cost only.

    Returns a dict mapping reachable hexes to their minimum cost from start_hex.
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

            if step_cost is None:
                step_total = neighbor_terrain_cost
            else:
                step_total = float(
                    step_cost(state, current_hex, neighbor, neighbor_terrain_cost)
                )
            if step_total == float("inf"):
                continue

            new_cost = current_cost + step_total

            if new_cost > max_cost:
                continue

            occ = state.board.active_units_at_hex(neighbor)
            if occ:
                # No stacking configured: occupied hexes are impassable.
                if max_active_units_per_hex is None:
                    continue
                if moving_faction is None:
                    continue
                if any(u.faction != moving_faction for u in occ):
                    continue
            if new_cost < costs.get(neighbor, float("inf")):
                costs[neighbor] = new_cost
                counter += 1
                heapq.heappush(heap, (new_cost, counter, neighbor))

    return costs


def shortest_move_path(
    state: GameState,
    unit_id: str,
    target_hex: Hex,
    movement_budget: float,
    *,
    zoc_hexes: frozenset[Hex] | None = None,
    blocked_hexes: frozenset[Hex] | None = None,
    max_active_units_per_hex: int | None = None,
    step_cost: Callable[[GameState, Hex, Hex, float], float] | None = None,
) -> tuple[Hex, ...] | None:
    """Minimum-cost path for a unit to `target_hex` under `compute_reachable_hexes` rules.

    Returns start-to-target hex tuples inclusive, or `None` if unreachable within budget.
    Tie-breaking matches Dijkstra's first-found minimal cost per hex.
    """
    unit = state.board.units.get(unit_id)
    if unit is None or not unit.active:
        return None
    start_hex = unit.position
    if start_hex == target_hex:
        return (start_hex,)

    moving_faction = unit.faction
    costs: dict[Hex, float] = {start_hex: 0.0}
    came_from: dict[Hex, Hex | None] = {start_hex: None}

    counter = 0
    heap: list[tuple[float, int, Hex]] = [(0.0, counter, start_hex)]

    while heap:
        current_cost, _, current_hex = heapq.heappop(heap)

        if current_cost > costs.get(current_hex, float("inf")):
            continue

        if (
            blocked_hexes is not None
            and current_hex in blocked_hexes
            and current_hex != start_hex
        ):
            continue

        if (
            zoc_hexes is not None
            and current_hex in zoc_hexes
            and current_hex != start_hex
        ):
            continue

        for neighbor in neighbors(current_hex):
            if (
                blocked_hexes is not None
                and neighbor in blocked_hexes
                and neighbor != start_hex
            ):
                continue
            neighbor_terrain_cost = state.board.get_movement_cost(neighbor)
            if neighbor_terrain_cost == float("inf"):
                continue

            if step_cost is None:
                step_total = neighbor_terrain_cost
            else:
                step_total = float(
                    step_cost(state, current_hex, neighbor, neighbor_terrain_cost)
                )
            if step_total == float("inf"):
                continue

            new_cost = current_cost + step_total
            if new_cost > movement_budget:
                continue

            occ = state.board.active_units_at_hex(neighbor)
            if occ:
                if max_active_units_per_hex is None:
                    continue
                if any(u.faction != moving_faction for u in occ):
                    continue
            if new_cost < costs.get(neighbor, float("inf")):
                costs[neighbor] = new_cost
                came_from[neighbor] = current_hex
                counter += 1
                heapq.heappush(heap, (new_cost, counter, neighbor))

    if target_hex not in costs:
        return None

    out: list[Hex] = []
    cur: Hex | None = target_hex
    while cur is not None:
        out.append(cur)
        cur = came_from.get(cur)
    out.reverse()
    if not out or out[0] != start_hex:
        return None
    if max_active_units_per_hex is not None:
        try:
            lim = int(max_active_units_per_hex)
        except (TypeError, ValueError):
            lim = 0
        if (
            lim > 0
            and target_hex != start_hex
            and len(state.board.active_units_at_hex(target_hex)) >= lim
        ):
            return None
    return tuple(out)


def compute_valid_moves(
    state: GameState,
    unit_id: str,
    movement_budget: float,
    *,
    zoc_hexes: frozenset[Hex] | None = None,
    blocked_hexes: frozenset[Hex] | None = None,
    max_active_units_per_hex: int | None = None,
    step_cost: Callable[[GameState, Hex, Hex, float], float] | None = None,
) -> set[Hex]:
    """Compute valid movement hexes for a unit.

    state: current game state. unit_id: unit to compute moves for. movement_budget:
    maximum movement cost available.

    zoc_hexes: optional ZOC set for stop-on-entry (same semantics as compute_reachable_hexes).
    blocked_hexes: optional impassable hex set (same semantics as compute_reachable_hexes).

    Returns the set of hexes the unit can legally move to.
    """
    unit = state.board.units.get(unit_id)
    if unit is None or not unit.active:
        return set()

    reachable = compute_reachable_hexes(
        state,
        unit.position,
        movement_budget,
        moving_faction=unit.faction,
        zoc_hexes=zoc_hexes,
        blocked_hexes=blocked_hexes,
        max_active_units_per_hex=max_active_units_per_hex,
        step_cost=step_cost,
    )

    # Return just the hexes (not the costs)
    out = set(reachable.keys())
    if max_active_units_per_hex is not None:
        try:
            lim = int(max_active_units_per_hex)
        except (TypeError, ValueError):
            lim = 0
        if lim > 0:
            out = {
                h
                for h in out
                if h == unit.position or len(state.board.active_units_at_hex(h)) < lim
            }
    return out


def is_valid_move(
    state: GameState,
    unit_id: str,
    target_hex: Hex,
    movement_budget: float,
    *,
    zoc_hexes: frozenset[Hex] | None = None,
    blocked_hexes: frozenset[Hex] | None = None,
    max_active_units_per_hex: int | None = None,
    step_cost: Callable[[GameState, Hex, Hex, float], float] | None = None,
) -> bool:
    """Check if a specific move is valid.

    state, unit_id, target_hex, movement_budget as for compute_valid_moves.

    zoc_hexes and blocked_hexes: optional sets with the same semantics as compute_valid_moves.

    Returns True if the move is valid, False otherwise.
    """
    return target_hex in compute_valid_moves(
        state,
        unit_id,
        movement_budget,
        zoc_hexes=zoc_hexes,
        blocked_hexes=blocked_hexes,
        max_active_units_per_hex=max_active_units_per_hex,
        step_cost=step_cost,
    )


def compute_retreat_destination_hexes(
    state: GameState,
    unit_id: str,
    required_steps: int,
    movement_budget: float,
    *,
    zoc_hexes: frozenset[Hex] | None = None,
    blocked_hexes: frozenset[Hex] | None = None,
    max_active_units_per_hex: int | None = None,
    step_cost: Callable[[GameState, Hex, Hex, float], float] | None = None,
) -> set[Hex]:
    """
    Hexes reachable as a retreat fulfillment: graph reachability within budget and
    cube distance from the unit's current hex exactly equals required_steps.

    When zoc_hexes is passed, applies the same stop-on-entry rule as normal movement.
    Callers may pass None for mandatory retreat so multi-hex paths stay legal.
    When blocked_hexes is passed, treats those hexes as impassable (except start).
    """
    unit = state.board.units.get(unit_id)
    if unit is None or not unit.active:
        return set()
    start = unit.position
    reachable = compute_reachable_hexes(
        state,
        start,
        movement_budget,
        moving_faction=unit.faction,
        zoc_hexes=zoc_hexes,
        blocked_hexes=blocked_hexes,
        max_active_units_per_hex=max_active_units_per_hex,
        step_cost=step_cost,
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
            max_active_units_per_hex=max_active_units_per_hex,
            step_cost=step_cost,
        ):
            out.add(h)
    return out
