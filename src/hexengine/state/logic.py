"""
Game logic utilities for computing state-derived information.

These are pure functions that compute things like valid moves,
line of sight, etc. from game state without modifying it.
"""

import heapq
from typing import Set

from ..hexes.math import neighbors
from ..hexes.types import Hex
from ..state.game_state import GameState


def compute_reachable_hexes(state: GameState, start_hex: Hex, max_cost: float) -> dict[Hex, float]:
    """Calculate all hexes reachable from start_hex within max_cost.
    
    Uses Dijkstra's algorithm to find the minimum cost path to each reachable hex.
    Takes into account terrain costs and occupied hexes.
    
    Args:
        state: Current game state
        start_hex: Starting hex position
        max_cost: Maximum movement cost budget
    
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
        
        # Explore all neighboring hexes
        for neighbor in neighbors(current_hex):
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


def compute_valid_moves(state: GameState, unit_id: str, movement_budget: float) -> Set[Hex]:
    """Compute valid movement hexes for a unit.
    
    Args:
        state: Current game state
        unit_id: ID of the unit to compute moves for
        movement_budget: Maximum movement cost available
    
    Returns:
        Set of hexes the unit can legally move to
    """
    unit = state.board.units.get(unit_id)
    if unit is None or not unit.active:
        return set()
    
    reachable = compute_reachable_hexes(state, unit.position, movement_budget)
    
    # Return just the hexes (not the costs)
    return set(reachable.keys())


def is_valid_move(state: GameState, unit_id: str, target_hex: Hex, movement_budget: float) -> bool:
    """Check if a specific move is valid.
    
    Args:
        state: Current game state
        unit_id: ID of the unit to move
        target_hex: Target hex position
        movement_budget: Maximum movement cost available
    
    Returns:
        True if the move is valid, False otherwise
    """
    return target_hex in compute_valid_moves(state, unit_id, movement_budget)
