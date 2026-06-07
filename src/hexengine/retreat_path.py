"""Shared retreat path draft parsing and legality (map-selection preview + commit)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .hexes.math import distance, neighbors
from .hexes.types import Hex
from .state import GameState
from .state.logic import compute_reachable_hexes, is_valid_move


def hex_to_wire(h: Hex) -> dict[str, int]:
    return {"i": int(h.i), "j": int(h.j), "k": int(h.k)}


def hexes_to_wire(hexes: list[Hex]) -> list[dict[str, int]]:
    return [hex_to_wire(h) for h in hexes]


def parse_wire_path(raw: Any) -> tuple[Hex, ...]:
    if not isinstance(raw, list):
        return ()
    out: list[Hex] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        try:
            out.append(Hex(int(row["i"]), int(row["j"]), int(row["k"])))
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(out)


def path_from_draft(draft: Mapping[str, Any]) -> tuple[Hex, ...]:
    return parse_wire_path(draft.get("path"))


def can_complete_retreat_in_steps(
    dist_from_start: int, obligation: int, steps_remaining: int
) -> bool:
    """
    True when ``steps_remaining`` adjacency steps from a hex at cube distance
    ``dist_from_start`` can still end on the obligation ring.
    """
    if steps_remaining < 0:
        return False
    if steps_remaining == 0:
        return dist_from_start == obligation
    d = int(dist_from_start)
    k = int(steps_remaining)
    r = int(obligation)
    return abs(d - k) <= r <= d + k


def _step_movement_cost(
    state: GameState,
    from_hex: Hex,
    to_hex: Hex,
    step_cost: Callable[[GameState, Hex, Hex, float], float] | None,
) -> float:
    base = state.board.get_movement_cost(to_hex)
    if base == float("inf"):
        return float("inf")
    if step_cost is None:
        return float(base)
    return float(step_cost(state, from_hex, to_hex, base))


def _movement_cost_along_path(
    state: GameState,
    path: tuple[Hex, ...],
    step_cost: Callable[[GameState, Hex, Hex, float], float] | None,
) -> float:
    if len(path) < 2:
        return 0.0
    total = 0.0
    for i in range(len(path) - 1):
        c = _step_movement_cost(state, path[i], path[i + 1], step_cost)
        if c == float("inf"):
            return float("inf")
        total += c
    return total


def _can_complete_retreat_with_budget(
    *,
    state: GameState,
    start: Hex,
    from_hex: Hex,
    obligation: int,
    steps_remaining: int,
    budget_remaining: float,
    end: frozenset[Hex],
    step_cost: Callable[[GameState, Hex, Hex, float], float] | None,
) -> bool:
    """BFS: can we reach a valid end hex in exactly ``steps_remaining`` steps within budget?"""
    if steps_remaining < 0 or budget_remaining < 0:
        return False
    if steps_remaining == 0:
        return from_hex in end and distance(start, from_hex) == obligation

    # (hex, steps_used, cost_so_far)
    frontier: list[tuple[Hex, int, float]] = [(from_hex, 0, 0.0)]
    seen: set[tuple[Hex, int]] = {(from_hex, 0)}

    while frontier:
        h, used, cost = frontier.pop()
        if used == steps_remaining:
            if h in end and distance(start, h) == obligation:
                return True
            continue
        for n in neighbors(h):
            if distance(h, n) != 1:
                continue
            step = _step_movement_cost(state, h, n, step_cost)
            if step == float("inf"):
                continue
            new_cost = cost + step
            if new_cost > budget_remaining + 1e-9:
                continue
            new_used = used + 1
            key = (n, new_used)
            if key in seen:
                continue
            seen.add(key)
            frontier.append((n, new_used, new_cost))
    return False


def compute_retreat_path_highlight_sets(
    *,
    state: GameState,
    unit_id: str,
    obligation: int,
    player_faction: str,
    blocked_hexes: frozenset[Hex] | None,
    max_active_units_per_hex: int | None,
    step_cost: Callable[[GameState, Hex, Hex, float], float] | None,
) -> tuple[frozenset[Hex], frozenset[Hex]]:
    """
    Through and end hex sets for retreat path preview (same rules as unit drag retreat).

    End hexes are valid one-move retreat destinations at cube distance ``obligation`` from
    the unit start. Through hexes are other reachable hexes on the way (excluding start).
    """
    unit = state.board.units.get(unit_id)
    if unit is None or not unit.active:
        return frozenset(), frozenset()
    rem = int(obligation)
    if rem <= 0:
        return frozenset(), frozenset()
    start = unit.position
    budget = float(rem)
    reachable = compute_reachable_hexes(
        state,
        start,
        budget,
        moving_faction=unit.faction,
        zoc_hexes=None,
        blocked_hexes=blocked_hexes,
        max_active_units_per_hex=max_active_units_per_hex,
        step_cost=step_cost,
    )
    through: set[Hex] = set()
    end: set[Hex] = set()
    for h in reachable.keys():
        if any(x.faction != player_faction for x in state.board.active_units_at_hex(h)):
            continue
        if (
            max_active_units_per_hex is not None
            and len(state.board.active_units_at_hex(h)) >= max_active_units_per_hex
        ):
            continue
        if h != start:
            through.add(h)
        if distance(start, h) != rem:
            continue
        if is_valid_move(
            state,
            unit_id,
            h,
            budget,
            zoc_hexes=None,
            blocked_hexes=blocked_hexes,
            max_active_units_per_hex=max_active_units_per_hex,
            step_cost=step_cost,
        ):
            end.add(h)
    return frozenset(through), frozenset(end)


def legal_next_retreat_path_hexes(
    *,
    state: GameState,
    unit_id: str,
    path: tuple[Hex, ...],
    obligation: int,
    player_faction: str,
    blocked_hexes: frozenset[Hex] | None,
    max_active_units_per_hex: int | None,
    step_cost: Callable[[GameState, Hex, Hex, float], float] | None,
) -> list[Hex]:
    """
    Hexes the player may add next when extending a retreat path draft.

    A retreat must finish on the obligation ring (cube distance from start) in exactly
    ``obligation`` steps. Extensions are filtered so the draft can still complete under
    that step count and the movement budget (``obligation`` movement points).
    """
    unit = state.board.units.get(unit_id)
    if unit is None or not unit.active:
        return []
    start = unit.position
    rem = int(obligation)
    if rem <= 0:
        return []
    steps_done = max(0, len(path) - 1)
    if steps_done >= rem:
        return []
    if path and path[0] != start:
        return []

    through, end = compute_retreat_path_highlight_sets(
        state=state,
        unit_id=unit_id,
        obligation=rem,
        player_faction=player_faction,
        blocked_hexes=blocked_hexes,
        max_active_units_per_hex=max_active_units_per_hex,
        step_cost=step_cost,
    )

    tip = path[-1] if path else start
    path_set = frozenset(path)
    remaining = rem - steps_done
    budget = float(rem)
    prefix_cost = _movement_cost_along_path(state, path, step_cost)

    # From the start hex, any valid end destination is clickable (direct one-move retreat).
    if tip == start and steps_done == 0:
        legal: set[Hex] = set(end)
        for n in neighbors(start):
            if n in path_set or n in legal:
                continue
            step_cost_to_n = _step_movement_cost(state, start, n, step_cost)
            if step_cost_to_n == float("inf"):
                continue
            if prefix_cost + step_cost_to_n > budget + 1e-9:
                continue
            if n not in through:
                continue
            dist_n = distance(start, n)
            steps_after = remaining - 1
            budget_after = budget - prefix_cost - step_cost_to_n
            if not can_complete_retreat_in_steps(dist_n, rem, steps_after):
                continue
            if not _can_complete_retreat_with_budget(
                state=state,
                start=start,
                from_hex=n,
                obligation=rem,
                steps_remaining=steps_after,
                budget_remaining=budget_after,
                end=end,
                step_cost=step_cost,
            ):
                continue
            legal.add(n)
        return sorted(
            (h for h in legal if h not in path_set),
            key=lambda h: (h.i, h.j, h.k),
        )

    out: list[Hex] = []
    for n in neighbors(tip):
        if distance(tip, n) != 1 or n in path_set:
            continue

        step_cost_to_n = _step_movement_cost(state, tip, n, step_cost)
        if step_cost_to_n == float("inf"):
            continue
        if prefix_cost + step_cost_to_n > budget + 1e-9:
            continue

        dist_n = distance(start, n)
        steps_after = remaining - 1
        budget_after = budget - prefix_cost - step_cost_to_n

        if remaining == 1:
            if n in end:
                out.append(n)
            continue

        # Do not enter the destination ring until the final step.
        if dist_n == rem:
            continue
        if n not in through:
            continue
        if not can_complete_retreat_in_steps(dist_n, rem, steps_after):
            continue
        if not _can_complete_retreat_with_budget(
            state=state,
            start=start,
            from_hex=n,
            obligation=rem,
            steps_remaining=steps_after,
            budget_remaining=budget_after,
            end=end,
            step_cost=step_cost,
        ):
            continue
        out.append(n)

    return sorted(out, key=lambda h: (h.i, h.j, h.k))


def validate_retreat_path(
    *,
    state: GameState,
    unit_id: str,
    path: tuple[Hex, ...],
    obligation: int,
    blocked_hexes: frozenset[Hex] | None,
    max_active_units_per_hex: int | None,
    step_cost: Callable[[GameState, Hex, Hex, float], float] | None,
    validate_endpoint: Callable[[GameState, str, Hex, Hex, int], None],
) -> None:
    """Raise ValueError when the path is not a legal retreat fulfillment route."""
    unit = state.board.units.get(unit_id)
    if unit is None or not unit.active:
        raise ValueError("Unknown unit")
    start = unit.position
    rem = int(obligation)
    if rem <= 0:
        raise ValueError("No retreat obligation")
    if len(path) < 2:
        raise ValueError("Retreat path must include start and destination")
    if path[0] != start:
        raise ValueError("Retreat path must start at the unit position")
    if path[-1] == start:
        raise ValueError("Retreat path must leave the start hex")

    dest = path[-1]
    if distance(start, dest) != rem:
        raise ValueError(
            f"Retreat destination must be exactly {rem} hexes from the start"
        )

    if len(path) == 2:
        validate_endpoint(state, unit_id, start, dest, rem)
        return

    if len(path) - 1 != rem:
        raise ValueError(f"Retreat path must have exactly {rem} steps")
    for i in range(len(path) - 1):
        if distance(path[i], path[i + 1]) != 1:
            raise ValueError("Retreat path steps must be adjacent")
    validate_endpoint(state, unit_id, start, dest, rem)


__all__ = [
    "can_complete_retreat_in_steps",
    "compute_retreat_path_highlight_sets",
    "hex_to_wire",
    "hexes_to_wire",
    "legal_next_retreat_path_hexes",
    "parse_wire_path",
    "path_from_draft",
    "validate_retreat_path",
]
